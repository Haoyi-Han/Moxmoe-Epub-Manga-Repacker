import tomllib
from pathlib import Path
from argparse import Namespace
from typing import NamedTuple

from rich.console import Console

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
)

from .file_system import (
    check_if_path_string_valid,
    copy_dir_struct,
    copy_dir_struct_to_list,
    copy_dir_struct_ext_to_list,
    copy_file_timestamp,
    make_archive_threadsafe,
    remove_if_exists,
    unpack_archive_with_timestamp,
    PrettyDirectoryTree,
)

from .terminal_ui import log as tui_log, PathTable
from .comic_info import ComicInfoExtractor


class ComicFile:
    src_file: Path
    dst_file: Path
    cache_folder: Path

    def __init__(self, file_path: Path, in_dir: Path, out_dir: Path, cache_dir: Path):
        self.src_file = file_path
        relative_path = file_path.relative_to(in_dir)
        self.dst_file = out_dir / relative_path.with_suffix(".cbz")
        self.cache_folder = cache_dir / relative_path.with_suffix("")


class InitValidityChecker(NamedTuple):
    flag: bool
    name: str


class InvalidPathStringException(Exception):
    path_type: str
    message: str

    def __init__(
        self,
        path_type: str,
        message: str = "路径不合法、被占用或无权限，请检查配置文件或参数。",
    ):
        self.path_type = path_type
        self.message = path_type + message
        super().__init__(self.message)


class IRepacker:
    console: Console
    verbose: bool

    def __init__(self, verbose: bool = True, *, console: Console = None):
        self.verbose = verbose
        if console is not None:
            self.init_console(console)

    def init_console(self, console: Console):
        self.console = console

    def print(self, s, overflow: str = "fold"):
        self.console.print(s, overflow=overflow)

    def log(self, s: str, overflow: str = "fold"):
        if self.verbose:
            tui_log(self.console, s, overflow=overflow)


class Repacker(IRepacker):
    _input_dir: Path | None = None
    _output_dir: Path | None = None
    _cache_dir: Path | None = None
    _exclude_list: list[str] = []
    _filelist: list[ComicFile] = []

    def __init__(self, verbose: bool = True, console: Console = None):
        super().__init__(verbose, console=console)

    def init_data(self, config_path: str, args: Namespace):
        try:
            self.init_from_config(config_path)
            self.init_from_arguments(args.input_dir, args.output_dir, args.cache_dir)

            checked: InitValidityChecker = self.check_init_validity()
            if checked.flag is False:
                raise InvalidPathStringException(path_type=checked.name)

            self.init_filelist()

        except InvalidPathStringException:
            ...

    def init_from_arguments(
        self, input_dir: str | None, output_dir: str | None, cache_dir: str | None
    ):
        input_dir_obj: Path | None = check_if_path_string_valid(
            input_dir, check_only=True, force_create=False
        )
        output_dir_obj: Path | None = check_if_path_string_valid(
            output_dir, check_only=False, force_create=False
        )
        cache_dir_obj: Path | None = check_if_path_string_valid(
            cache_dir, check_only=False, force_create=True
        )
        if input_dir_obj is not None:
            self._input_dir = input_dir_obj
        if output_dir_obj is not None:
            self._output_dir = output_dir_obj
        if cache_dir_obj is not None:
            self._cache_dir = cache_dir_obj

    def init_from_config(self, config_path: str):
        self.log("[yellow]开始初始化程序...")

        # 用 tomllib 替代 ConfigParser 进行解析 20231207
        config_file = Path(config_path)
        with config_file.open("rb") as cf:
            config = tomllib.load(cf)

        input_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["InputDir"], check_only=True, force_create=False
        )
        output_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["OutputDir"], check_only=False, force_create=False
        )
        cache_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["CacheDir"], check_only=False, force_create=True
        )

        self._input_dir = input_dir_obj
        self._output_dir = output_dir_obj
        self._cache_dir = cache_dir_obj
        self._exclude_list = config["DEFAULT"]["Exclude"]

    def check_init_validity(self) -> InitValidityChecker:
        if self._input_dir is None:
            return InitValidityChecker(flag=False, name="输入目录")
        if self._output_dir is None:
            return InitValidityChecker(flag=False, name="输出目录")
        if self._cache_dir is None:
            return InitValidityChecker(flag=False, name="缓存目录")
        return InitValidityChecker(flag=True, name="")

    def init_filelist(self):
        self._filelist = self._init_path_obj(exclude=self._exclude_list)

    @property
    def input_dir(self) -> str:
        return str(self._input_dir)

    @property
    def output_dir(self) -> str:
        return str(self._output_dir)

    @property
    def cache_dir(self) -> str:
        return str(self._cache_dir)

    @property
    def filelist(self) -> list[ComicFile]:
        return self._filelist

    def repack(self, file_t: ComicFile):
        single_repacker = SingleRepacker(
            comic_file=file_t, console=self.console, verbose=self.verbose
        )
        single_repacker.pack_folder()

    def print_list(self):
        def new_comic_path(file_t: ComicFile) -> Path:
            single_repacker = SingleRepacker(
                comic_file=file_t, console=self.console, verbose=False
            )
            comic_name: str = single_repacker.comic_name
            path: Path = file_t.dst_file.parent / f"{comic_name}"
            relative_path = path.relative_to(self._output_dir.parent)
            return relative_path

        fake_list: list[Path] = list(map(new_comic_path, self.filelist))
        PrettyDirectoryTree(fake_list)

    # 初始化路径并复制目录结构
    def _init_path_obj(self, exclude=None) -> list[Path]:
        # 目录表格绘制
        if exclude is None:
            exclude = []
        if self.verbose:
            self.print(PathTable(self.input_dir, self.output_dir, self.cache_dir))
        # 文件列表抽取
        remove_if_exists(self.cache_dir)
        remove_if_exists(self.output_dir)
        raw_filelist: list[Path] = copy_dir_struct_ext_to_list(self.input_dir)
        filelist: list[ComicFile] = [
            ComicFile(
                file_path=f,
                in_dir=self._input_dir,
                out_dir=self._output_dir,
                cache_dir=self._cache_dir,
            )
            for f in raw_filelist
        ]
        self.log("[green]已完成文件列表抽取。")
        # 目录结构复制
        copy_dir_struct(self.input_dir, self.output_dir, exclude=exclude)
        self.log("[green]已完成目录结构复制。")
        return filelist


class SingleRepacker(IRepacker):
    _cache_dir: Path
    _zip_file: Path
    _cbz_file: Path
    _extract_dir: Path
    _pack_from_dir: Path
    _extractor: ComicInfoExtractor
    _comic_name: str

    def __init__(
        self, comic_file: ComicFile, verbose: bool = True, console: Console = None
    ):
        super().__init__(verbose, console=console)

        self._cache_dir = comic_file.cache_folder
        self._zip_file = comic_file.src_file
        self._cbz_file = comic_file.dst_file

        self._set_unique_extract_dir()
        self._pack_from_dir = self._load_zip_img()

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    @property
    def extract_dir(self) -> Path:
        return self._extract_dir

    @property
    def comic_name(self) -> str:
        return self._comic_name

    # 避免相同文件名解压到缓存文件夹时冲突
    def _set_unique_extract_dir(self) -> None:
        self._extract_dir = self.cache_dir / str(self._zip_file.stem)
        while self._extract_dir.is_dir():
            self._extract_dir = self.cache_dir / (str(self._zip_file.stem) + "_dup")

    def _analyse_archive(self) -> None:
        unpack_archive_with_timestamp(self._zip_file, extract_dir=self.extract_dir)
        opf_file = self.extract_dir / "vol.opf"
        self._extractor = ComicInfoExtractor(opf_file)
        self._comic_name = self._extractor.comic_file_name

    def _extract_images(self) -> None:
        for new_name, img_src in self._extractor.build_img_filelist(self.extract_dir):
            img_src.rename(Path(img_src.parent, f"{new_name}{img_src.suffix}"))

    def _organize_images(self, img_dir: Path, comic_name: str) -> Path:
        img_dir = img_dir.rename(Path(img_dir.parent, comic_name))
        img_filelist = copy_dir_struct_to_list(str(img_dir))
        for imgfile in img_filelist:
            imgstem = imgfile.stem
            if all(s not in imgstem for s in ["COVER", "END", "PAGE"]):
                imgfile.unlink()
        return img_dir

    # 增加 ComicInfo.xml 配置文件 20231212
    def _export_comicinfo_xml(self, xml_path: Path) -> None:
        self._extractor.comic_info.to_xml_file(xml_path)

    # 单个压缩包根据HTML文件中的图片地址进行提取
    # 拆分为多个小函数以提高可读性 20231212
    def _load_zip_img(self) -> Path:
        self.log(f"[yellow]开始解析 {self._zip_file.stem}")
        self._analyse_archive()

        self.log(f"{self.comic_name} => [yellow]开始提取")
        self._extract_images()

        img_dir = self.extract_dir / "image"
        img_dir = self._organize_images(img_dir, self.comic_name)

        comic_xml_path = img_dir / "ComicInfo.xml"
        self._export_comicinfo_xml(comic_xml_path)

        self.log(f"{self.comic_name} => [green]提取完成")
        return img_dir

    # 打包成压缩包并重命名
    # 修改输出路径为绝对路径，避免多次切换工作目录 20230429
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=(stop_after_attempt(5) | stop_after_delay(1.5)),
    )
    def pack_folder(self) -> Path:
        self.log(f"{self.comic_name} => [yellow]开始打包")

        self._cbz_file = self._cbz_file.parent / f"{self.comic_name}.cbz"
        comic_base: Path = self._cbz_file.with_suffix("")
        make_archive_threadsafe(
            comic_base,
            format="cbz",
            root_dir=self._pack_from_dir,
        )

        cbz_path = self._cbz_file

        # 修改新建立的 CBZ 文件时间戳为原 EPUB 文档内部的时间戳
        # 由于文档的时间戳随获取方式有别，故以文档内封面图片的时间戳为准
        comic_cover: Path = self._pack_from_dir / "cover.jpg"
        copy_file_timestamp(comic_cover, cbz_path)

        self.log(f"{self.comic_name} => [green]打包完成")
        return cbz_path
