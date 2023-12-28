import tomllib
import os
import shutil
from pathlib import Path

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


class IRepacker:
    def __init__(self, console: Console):
        self.console = console

    def print(self, s, overflow: str = "fold"):
        self.console.print(s, overflow=overflow)

    def log(self, s: str, overflow: str = "fold"):
        mtui.log(self.console, s, overflow=overflow)


class Repacker(IRepacker):
    _input_dir: str = ""
    _output_dir: str = ""
    _cache_dir: str = ""
    _filelist: list[Path]

    def __init__(self, console):
        super().__init__(console)

    def init_from_config(self, config_path: str):
        self.log("[yellow]开始初始化程序...")

        # 用 tomllib 替代 ConfigParser 进行解析 20231207
        config_file = Path(config_path)
        with config_file.open("rb") as cf:
            config = tomllib.load(cf)

        self._input_dir = config["DEFAULT"]["InputDir"]
        self._output_dir = config["DEFAULT"]["OutputDir"]
        self._cache_dir = config["DEFAULT"]["CacheDir"]
        self._filelist = self._init_path_obj(exclude=config["DEFAULT"]["Exclude"])

    @property
    def input_dir(self) -> str:
        return self._input_dir

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @property
    def cache_dir(self) -> str:
        return self._cache_dir

    @property
    def filelist(self) -> list[Path]:
        return self._filelist

    def repack(self, file):
        file_t = Path(file)
        comic_name: str = file_t.parents[0].name
        single_repacker = SingleRepacker(self.cache_dir, file_t, self.console)
        real_output_dir = Path(self.output_dir)
        if comic_name != Path(self.input_dir).stem:
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
    _cache_dir: str = ""
    _zip_file: Path
    _extract_dir: Path
    _pack_from_dir: Path
    _extractor: mcif.ComicInfoExtractor
    _comic_name: str

    def __init__(self, cache_dir: str, zip_file: Path, console):
        super().__init__(console)
        self._cache_dir = cache_dir
        self._zip_file = zip_file

        self._set_unique_extract_dir()
        self._pack_from_dir = self._load_zip_img()

    @property
    def cache_dir(self) -> str:
        return self._cache_dir

    @property
    def extract_dir(self) -> Path:
        return self._extract_dir

    @property
    def comic_name(self) -> str:
        return self._comic_name

    # 避免相同文件名解压到缓存文件夹时冲突
    def _set_unique_extract_dir(self) -> None:
        self._extract_dir = Path(self.cache_dir, str(self._zip_file.stem))
        while self._extract_dir.is_dir():
            self._extract_dir = Path(self.cache_dir, str(self._zip_file.stem) + "_dup")

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
