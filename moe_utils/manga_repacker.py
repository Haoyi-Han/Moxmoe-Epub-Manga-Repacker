import tomllib
import os
import shutil
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

import moe_utils.file_system as mfst
import moe_utils.terminal_ui as mtui
import moe_utils.comic_info as mcif


class InitValidityChecker(NamedTuple):
    flag: bool
    name: str


class InvalidPathStringException(Exception):
    path_type: str
    message: str
    
    def __init__(self, path_type: str, message: str = "路径不合法、被占用或无权限，请检查配置文件或参数。"):
        self.path_type = path_type
        self.message = path_type + message
        super().__init__(self.message)


class IRepacker:
    def __init__(self, console: Console):
        self.console = console

    def print(self, s, overflow: str = "fold"):
        self.console.print(s, overflow=overflow)

    def log(self, s: str, overflow: str = "fold"):
        mtui.log(self.console, s, overflow=overflow)


class Repacker(IRepacker):
    _input_dir: Path | None = None
    _output_dir: Path | None = None
    _cache_dir: Path | None = None
    _exclude_list: list[str] = []
    _filelist: list[Path] = []

    def __init__(self, console):
        super().__init__(console)

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
        input_dir_obj: Path | None = mfst.check_if_path_string_valid(
            input_dir, check_only=True, force_create=False
        )
        output_dir_obj: Path | None = mfst.check_if_path_string_valid(
            output_dir, check_only=False, force_create=False
        )
        cache_dir_obj: Path | None = mfst.check_if_path_string_valid(
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

        input_dir_obj: Path | None = mfst.check_if_path_string_valid(
            config["DEFAULT"]["InputDir"], check_only=True, force_create=False
        )
        output_dir_obj: Path | None = mfst.check_if_path_string_valid(
            config["DEFAULT"]["OutputDir"], check_only=False, force_create=False
        )
        cache_dir_obj: Path | None = mfst.check_if_path_string_valid(
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
    def filelist(self) -> list[Path]:
        return self._filelist

    def repack(self, file_t: Path):
        comic_name: str = file_t.parents[0].name
        single_repacker = SingleRepacker(self._cache_dir, file_t, self.console)
        real_output_dir: Path = self._output_dir
        if comic_name != self._input_dir.stem:
            real_output_dir = real_output_dir / comic_name
        single_repacker.pack_folder(real_output_dir)

    # 初始化路径并复制目录结构
    def _init_path_obj(self, exclude=None) -> list[Path]:
        # 目录表格绘制
        if exclude is None:
            exclude = []
        self.print(mtui.PathTable(self.input_dir, self.output_dir, self.cache_dir))
        # 文件列表抽取
        mfst.remove_if_exists(self.cache_dir)
        mfst.remove_if_exists(self.output_dir)
        filelist: list[Path] = mfst.copy_dir_struct_ext_to_list(self.input_dir)
        self.log("[green]已完成文件列表抽取。")
        # 目录结构复制
        mfst.copy_dir_struct(self.input_dir, self.output_dir, exclude=exclude)
        self.log("[green]已完成目录结构复制。")
        return filelist


class SingleRepacker(IRepacker):
    _cache_dir: Path
    _zip_file: Path
    _extract_dir: Path
    _pack_from_dir: Path
    _extractor: mcif.ComicInfoExtractor
    _comic_name: str

    def __init__(self, cache_dir: Path, zip_file: Path, console):
        super().__init__(console)
        self._cache_dir = cache_dir
        self._zip_file = zip_file

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
        shutil.unpack_archive(
            str(self._zip_file), extract_dir=self.extract_dir, format="zip"
        )
        opf_file = self.extract_dir / "vol.opf"
        self._extractor = mcif.ComicInfoExtractor(opf_file)
        self._comic_name = self._extractor.comic_file_name

    def _extract_images(self) -> None:
        for new_name, img_src in self._extractor.build_img_filelist(self.extract_dir):
            img_src.rename(Path(img_src.parent, f"{new_name}{img_src.suffix}"))

    def _organize_images(self, img_dir: Path, comic_name: str) -> Path:
        img_dir = img_dir.rename(Path(img_dir.parent, comic_name))
        img_filelist = mfst.copy_dir_struct_to_list(str(img_dir))
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
    # 用 shutil.make_archive() 代替 zipFile，压缩体积更小
    # 修改输出路径为绝对路径，避免多次切换工作目录 20230429
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=(stop_after_attempt(5) | stop_after_delay(1.5)),
    )
    def pack_folder(self, out_dir: Path, ext: str = ".cbz") -> Path:
        self.log(f"{self.comic_name} => [yellow]开始打包")
        shutil.make_archive(
            os.path.join(out_dir, self.comic_name),
            format="zip",
            root_dir=self._pack_from_dir,
        )
        zip_path = Path(out_dir, self.comic_name + ".zip")
        cbz_path = zip_path.rename(zip_path.with_suffix(ext))
        self.log(f"{self.comic_name} => [green]打包完成")
        return cbz_path
