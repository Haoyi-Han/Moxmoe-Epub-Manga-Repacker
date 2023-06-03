import configparser as cp
import os
import re
import shutil
from pathlib import Path
from typing import Any, Union

import retry
from bs4 import BeautifulSoup

import moe_utils.file_system as mfst
import moe_utils.terminal_ui as mtui
import moe_utils.utils as mutl


class Repacker:
    def __init__(self, console, ui_active: bool = False, logger=None):
        self._inputDir = ''
        self._outputDir = ''
        self._cacheDir = ''
        self._fileList = []
        self.console = console
        self.ui_active = ui_active
        self.logger = logger

    def initFromConfig(self, config_path: str):
        self.log(f'[yellow]开始初始化程序...')
        config = cp.ConfigParser()
        config.read(config_path, encoding='utf-8')

        self._inputDir = config['DEFAULT']['InputDir']
        self._outputDir = config['DEFAULT']['OutputDir']
        self._cacheDir = config['DEFAULT']['CacheDir']
        self._fileList = self._initPathObj(exclude=config['DEFAULT']['Exclude'].split('||'))

    @property
    def inputDir(self):
        return self._inputDir

    @property
    def outputDir(self):
        return self._outputDir

    @property
    def cacheDir(self):
        return self._cacheDir

    @property
    def fileList(self):
        return self._fileList

    def print(self, s, overflow="fold"):
        if self.ui_active:
            self.logger.write(s)
        else:
            self.console.print(s, overflow=overflow)

    def log(self, s: str, overflow="fold"):
        mtui.log(self.console, s, overflow=overflow)

    def repack(self, file):
        file_t = Path(file)
        comic_name: str = file_t.parents[0].name
        comic_src = self._loadZipImg(file_t)
        if comic_name == Path(self.inputDir).stem:
            self._packFolder(comic_src, Path(self.outputDir))
        else:
            self._packFolder(comic_src, Path(self.outputDir) / comic_name)

    # 初始化路径并复制目录结构
    def _initPathObj(
            self,
            exclude=None
    ) -> list:
        # 目录表格绘制
        if exclude is None:
            exclude = []
        self.print(mtui.PathTable(
            self.inputDir,
            self.outputDir,
            self.cacheDir
        ))
        # 文件列表抽取
        mfst.removeIfExists(self.cacheDir)
        mfst.removeIfExists(self.outputDir)
        filelist: list = mfst.copyDirStructExtToList(self.inputDir)
        self.log(f"[green]已完成文件列表抽取。")
        # 目录结构复制
        mfst.copyDirStruct(self.inputDir, self.outputDir, exclude=exclude)
        self.log(f"[green]已完成目录结构复制。")
        return filelist

    # HTML 按照 vol.opf 中规定的顺序抽取成列表
    # 本函数是为 Mox.moe 新发布的文件设计，但兼容老版本
    # 以解决新版本文件中网页顺序打乱导致图片顺序错乱问题
    @staticmethod
    def _htmlObjExtract(
            curr_page: dict[str, Union[str, Any]],
            extract_dir: Path,
            length: int) -> tuple:
        idx = curr_page['id'].replace('Page_', '')
        file_stem = re.findall(r'[^/]+\.html', curr_page['href'])[0]
        raw_path = extract_dir / 'html' / file_stem
        if 'cover' == idx:
            return 0, raw_path
        elif idx.isnumeric():
            return int(idx), raw_path
        else:
            # 'createby' == id
            return length, raw_path

    def _htmlExtractToList(
            self,
            extract_dir: Path,
            soup: BeautifulSoup
    ) -> list:
        raw_pages = soup.package.manifest.find_all('item', {'media-type': 'application/xhtml+xml'})
        reduced_pages = sorted(
            map(lambda pg: self._htmlObjExtract(pg, extract_dir, len(raw_pages)), raw_pages),
            key=lambda x: x[0]
        )
        return list(zip(*reduced_pages))[1]

    # 新的漫画名称抽取函数 20230528
    @staticmethod
    def _comicNameExtract(soup: BeautifulSoup) -> str:
        author: str = soup.package.metadata.find('dc:creator').string
        title, volume = soup.package.metadata.find('dc:title').string.split(' - ')
        return f'[{author}][{title}]{volume}'

    # 单个压缩包根据HTML文件中的图片地址进行提取
    def _loadZipImg(self, zip_file) -> Path:
        self.log(f'[yellow]开始解析 {zip_file.stem}')
        # 避免相同文件名解压到缓存文件夹时冲突
        extract_dir = Path(self.cacheDir, str(zip_file.stem))
        while extract_dir.is_dir():
            extract_dir = Path(self.cacheDir, str(zip_file.stem) + '_dup')
        shutil.unpack_archive(str(zip_file), extract_dir=extract_dir, format="zip")
        opf_file = extract_dir / 'vol.opf'
        soup_0 = mutl.readXmlFile(opf_file)
        comic_name: str = self._comicNameExtract(soup_0)
        self.log(f'{comic_name} => [yellow]开始提取')
        img_dir = extract_dir / 'image'
        html_list: list = self._htmlExtractToList(extract_dir, soup_0)
        for html_file in html_list:
            soup = mutl.readHtmlFile(html_file)
            title: str = soup.title.string
            imgsrc = Path(soup.img['src'])
            imgsrc = img_dir / imgsrc.name
            if 'cover' in imgsrc.name:
                imgsrc.rename(Path(imgsrc.parent, 'COVER' + imgsrc.suffix))
            elif 'END' in title:
                imgsrc.rename(Path(imgsrc.parent, 'THE END' + imgsrc.suffix))
            else:
                page_num: str = re.search(r'\d+', title).group(0)
                imgsrc.rename(Path(imgsrc.parent, 'PAGE {:03}'.format(int(page_num)) + imgsrc.suffix))
        img_dir = img_dir.rename(Path(img_dir.parent, comic_name))
        img_filelist = mfst.copyDirStructToList(str(img_dir))
        for file in img_filelist:
            imgfile = Path(file)
            imgstem = imgfile.stem
            if all(s not in imgstem for s in ['COVER', 'END', 'PAGE']):
                imgfile.unlink()
        self.log(f'{comic_name} => [green]提取完成')
        return img_dir

    # 打包成压缩包并重命名
    # 用 shutil.make_archive() 代替 zipFile，压缩体积更小
    # 修改输出路径为绝对路径，避免多次切换工作目录 20230429
    @retry.retry(Exception, tries=5, delay=0.5)
    def _packFolder(
            self,
            inDir: Path,
            outDir: Path,
            ext: str = '.cbz'
    ) -> Path:
        comic_name: str = inDir.name
        self.log(f'{comic_name} => [yellow]开始打包')
        shutil.make_archive(os.path.join(outDir, comic_name), format='zip', root_dir=inDir)
        zip_path = Path(outDir, comic_name + '.zip')
        cbz_path = zip_path.rename(zip_path.with_suffix(ext))
        self.log(f'{comic_name} => [green]打包完成')
        return cbz_path
