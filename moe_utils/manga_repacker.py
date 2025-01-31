import zipfile
from fnmatch import fnmatch
from io import TextIOWrapper
from pathlib import Path
from typing import NamedTuple

import tomllib
from rich.console import Console, OverflowMethod
from rich.prompt import Prompt
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    stop_after_delay,
)

from .comic_info import ComicInfoExtractor
from .file_system import (
    Extern7z,
    GeneralPath,
    GeneralPathUnwrapped,
    check_if_path_string_valid,
    copy_dir_struct,
    copy_dir_struct_ext_to_list,
    copy_dir_struct_to_list,
    copy_file_timestamp,
    is_dir_nonexistent_or_empty,
    make_archive_threadsafe,
    print_dir_tree,
    remove_if_exists,
    unpack_archive_with_timestamp,
)
from .terminal_ui import DynamicLogger, PathTable, tui_log, tui_print


class ComicFile:
    src_file: Path
    dst_file: Path
    cache_folder: Path
    relative_path: Path

    def __init__(
        self,
        file_path: Path | None,
        in_dir: Path | None,
        out_dir: Path | None,
        cache_dir: Path | None,
    ):
        assert file_path is not None
        assert in_dir is not None
        assert out_dir is not None
        assert cache_dir is not None
        self.src_file = file_path
        self.relative_path = file_path.relative_to(in_dir)
        self.dst_file = out_dir / self.relative_path.with_suffix(".cbz")
        self.cache_folder = cache_dir / self.relative_path.with_suffix("")


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
    _use_extern_7z: bool = False
    _extern_7z: Extern7z | None = None

    def __init__(
        self,
        verbose: bool = True,
        *,
        console: Console | None = None,
        sevenz: Extern7z | GeneralPath = None,
        dlogger: DynamicLogger | None = None,
    ):
        self.verbose = verbose
        self.dlogger = dlogger

        if console is not None:
            self.init_console(console)
            self.status = self.console.status("")

        if sevenz is not None:
            self.init_sevenz(sevenz)

    def init_console(self, console: Console):
        self.console = console

    def init_sevenz(self, sevenz: Extern7z | GeneralPathUnwrapped):
        if isinstance(sevenz, Extern7z):
            self._extern_7z = sevenz
        elif isinstance(sevenz, GeneralPath):
            self._extern_7z = Extern7z(sevenz)

        if self._extern_7z is None:
            self._use_extern_7z = False
        elif not self._extern_7z.check_7z_availability():
            self._use_extern_7z = False
        else:
            self._use_extern_7z = True

    def print(self, s, *, overflow: OverflowMethod = "fold"):
        tui_print(self.console, s, overflow=overflow)

    def log(self, s: str, *, overflow: OverflowMethod = "fold"):
        tui_log(self.console, s, overflow=overflow, verbose=self.verbose)


class Repacker(IRepacker):
    _input_dir: Path | None = None
    _output_dir: Path | None = None
    _cache_dir: Path | None = None
    _exclude_list: list[str] = []
    _filelist: list[ComicFile] = []
    _faillist: list[ComicFile] = []

    def __init__(self, verbose: bool = True, console: Console | None = None, dlogger: DynamicLogger | None = None):
        super().__init__(verbose, console=console, sevenz=None, dlogger=dlogger)

    def init_data(self, config_path: str = "config.toml", init_filelist_flag: bool = True, ignore_clean: bool = False):
        try:
            self.init_from_config(config_path)

            checked: InitValidityChecker = self.check_init_validity()
            if checked.flag is False:
                raise InvalidPathStringException(path_type=checked.name)

            if init_filelist_flag:
                self.init_filelist(ignore_clean=ignore_clean)

        except InvalidPathStringException:
            ...

    def init_from_config(self, config_path: str):
        # 用 tomllib 替代 ConfigParser 进行解析 20231207
        config_file = Path(config_path)
        with config_file.open("rb") as cf:
            config = tomllib.load(cf)

        input_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["input_dir"], check_only=True, force_create=False
        )
        output_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["output_dir"], check_only=False, force_create=False
        )
        cache_dir_obj: Path | None = check_if_path_string_valid(
            config["DEFAULT"]["cache_dir"], check_only=False, force_create=True
        )

        self._input_dir = input_dir_obj
        self._output_dir = output_dir_obj
        self._cache_dir = cache_dir_obj
        self._exclude_list = config["DEFAULT"]["exclude"]

        def _set_use_extern_7z_switch() -> bool:
            use_extern_7z: bool = config["DEFAULT"]["enable_extern_7z_use"]
            if not use_extern_7z:
                return False
            sevenz_exec: str = config["DEFAULT"]["extern_7z_executable_path"]
            self._extern_7z = Extern7z(sevenz_exec)
            use_extern_7z = self._extern_7z.check_7z_availability()
            if use_extern_7z:
                return True
            self._extern_7z = Extern7z()
            use_extern_7z = self._extern_7z.check_7z_availability()
            return use_extern_7z

        self._use_extern_7z = _set_use_extern_7z_switch()

    def check_init_validity(self) -> InitValidityChecker:
        if self._input_dir is None:
            return InitValidityChecker(flag=False, name="输入目录")
        if self._output_dir is None:
            return InitValidityChecker(flag=False, name="输出目录")
        if self._cache_dir is None:
            return InitValidityChecker(flag=False, name="缓存目录")
        return InitValidityChecker(flag=True, name="")

    def init_filelist(self, ignore_clean: bool = False):
        self._filelist = self._init_path_obj(exclude=self._exclude_list, ignore_clean=ignore_clean)

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

    @property
    def faillist(self) -> list[ComicFile]:
        return self._faillist

    def repack(self, file_t: ComicFile):
        sevenz: Extern7z | None = None
        if self._use_extern_7z:
            sevenz = self._extern_7z
        try:
            single_repacker = SingleRepacker(
                comic_file=file_t,
                console=self.console,
                verbose=self.verbose,
                sevenz=sevenz,
                dlogger=self.dlogger,
            )
            single_repacker.pack_folder()
        except Exception as e:
            self.log(f"[red]⚠️ 错误[/]：{e}")
            self._faillist.append(file_t)

    def print_list(self):
        def new_comic_path(file_t: ComicFile) -> Path:
            single_repacker = SingleRepacker(
                comic_file=file_t,
                no_work=True,
                verbose=False,
                console=self.console,
                dlogger=self.dlogger,
            )
            comic_name: str = single_repacker.comic_name
            path: Path = file_t.dst_file.parent / f"{comic_name}"
            relative_path = path.relative_to(self._output_dir.parent)
            return relative_path

        fake_list: list[Path] = list(map(new_comic_path, self.filelist))
        print_dir_tree(fake_list, self.console)

    def clean_cache(self, verbose: bool = True):
        remove_if_exists(self.cache_dir)

    def clean_input(self, verbose: bool = True):
        remove_if_exists(self.input_dir, recreate=True)

    def clean_output(self, verbose: bool = True):
        remove_if_exists(self.output_dir, recreate=True)

    # 初始化路径并复制目录结构
    def _init_path_obj(self, exclude=None, ignore_clean: bool = False) -> list[ComicFile]:
        # 目录表格绘制
        if exclude is None:
            exclude = []
        if self.verbose:
            self.print(PathTable(self.input_dir, self.output_dir, self.cache_dir))
        # 文件列表抽取
        if not ignore_clean:
            if (self._cache_dir is None) or is_dir_nonexistent_or_empty(self._cache_dir):
                clean_cache_flag = False
            else:
                clean_cache_flag = Prompt.ask("请选择是否清空缓存文件夹", choices=["y", "n"], default="y")
            if (self._output_dir is None) or is_dir_nonexistent_or_empty(self._output_dir):
                clean_output_flag = False
            else:
                clean_output_flag = Prompt.ask("请选择是否清空输出文件夹", choices=["y", "n"], default="y")
            if clean_cache_flag:
                self.clean_cache(verbose=False)
            if clean_output_flag:
                self.clean_output(verbose=False)
            if not self._cache_dir.exists():
                self._cache_dir.mkdir(parents=True, exist_ok=True)
            if not self._output_dir.exists():
                self._output_dir.mkdir(parents=True, exist_ok=True)

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
        self.log("[green]✅ 已完成文件列表抽取。")
        # 目录结构复制
        copy_dir_struct(self.input_dir, self.output_dir, exclude=exclude)
        self.log("[green]✅ 已完成目录结构复制。")
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
        self,
        comic_file: ComicFile,
        no_work: bool = False,
        verbose: bool = True,
        console: Console | None = None,
        sevenz: GeneralPath | Extern7z = None,
        dlogger: DynamicLogger | None = None,
    ):
        super().__init__(verbose, console=console, sevenz=sevenz, dlogger=dlogger)

        self._cache_dir = comic_file.cache_folder
        self._zip_file = comic_file.src_file
        self._cbz_file = comic_file.dst_file

        if no_work:
            self._analyse_archive()
        else:
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
        self._extract_dir = self.cache_dir
        while self._extract_dir.is_dir():
            self._extract_dir = self.cache_dir.with_suffix(".1")

    # 解压前单独访问 opf 文件获取元数据
    # https://stackoverflow.com/questions/20601796/how-to-open-an-unicode-text-file-inside-a-zip
    def _extract_opf_from_epub(self, epub_file: str | Path, opf_name: str = "vol.opf") -> str:
        with zipfile.ZipFile(str(epub_file), "r") as zip_ref:
            with zip_ref.open(opf_name, "r") as opf_file:
                text: str = ""
                for line in TextIOWrapper(opf_file, encoding="utf-8"):
                    text += line
                return text

    def _analyse_archive(self) -> None:
        opf_text: str = self._extract_opf_from_epub(self._zip_file, "vol.opf")
        self._extractor = ComicInfoExtractor(use_text=True, opf_text=opf_text)
        self._comic_name = self._extractor.comic_file_name

    def _extract_archive(self) -> None:
        if self._use_extern_7z:
            self._extern_7z.unpack_archive(self._zip_file, extract_dir=self.extract_dir, no_root=False)
        else:
            unpack_archive_with_timestamp(
                self._zip_file,
                extract_dir=self.extract_dir,
                filters=["html/", "image/"],
            )

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
        self.status.update(f"[yellow]⏳ 开始解析 {self._zip_file.stem}")
        self._analyse_archive()
        self._extract_archive()

        self.status.update(f"⏳ {self.comic_name} => [yellow]开始提取")
        self._extract_images()

        img_dir = self.extract_dir / "image"
        img_dir = self._organize_images(img_dir, self.comic_name)

        comic_xml_path = img_dir / "ComicInfo.xml"
        self._export_comicinfo_xml(comic_xml_path)

        self.dlogger.update_log(f"✅ {self.comic_name} => [green]提取完成")
        return img_dir

    # 打包成压缩包并重命名
    # 修改输出路径为绝对路径，避免多次切换工作目录 20230429
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=(stop_after_attempt(5) | stop_after_delay(1.5)),
    )
    def pack_folder(self) -> Path:
        self.status.update(f"⏳ {self.comic_name} => [yellow]开始打包")

        self._cbz_file = self._cbz_file.parent / f"{self.comic_name}.cbz"
        comic_base: Path = self._cbz_file.with_suffix("")

        # 由于文档的时间戳随获取方式有别，故以文档内封面图片的时间戳为准
        comic_cover = next(
            f for f in self._pack_from_dir.glob("*") if fnmatch(f.name, "[Cc][Oo][Vv][Ee][Rr].[Jj][Pp][Gg]")
        )

        # 修改漫画文件夹时间戳为原 EPUB 文档内部的时间戳
        copy_file_timestamp(comic_cover, self._pack_from_dir)

        if self._use_extern_7z:
            self._extern_7z.make_archive(self._cbz_file, root_dir=self._pack_from_dir)
        else:
            make_archive_threadsafe(
                comic_base,
                format="cbz",
                root_dir=self._pack_from_dir,
            )

        cbz_path = self._cbz_file

        # 修改新建立的 CBZ 文件时间戳为原 EPUB 文档内部的时间戳
        copy_file_timestamp(comic_cover, cbz_path)

        self.dlogger.update_log(f"✅ {self.comic_name} => [green]打包完成")

        return cbz_path
