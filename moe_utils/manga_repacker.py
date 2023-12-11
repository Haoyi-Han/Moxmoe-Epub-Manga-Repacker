import tomllib
import os
import re
import shutil
from pathlib import Path
from typing import Any, Union

from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, stop_after_delay

import moe_utils.file_system as mfst
import moe_utils.terminal_ui as mtui
import moe_utils.utils as mutl
import moe_utils.comic_info as mcif


class Repacker:
    _inputDir: str = ''
    _outputDir: str = ''
    _cacheDir: str = ''
    _fileList: list

    def __init__(self, console):
        self.console = console

    def initFromConfig(self, config_path: str):
        self.log('[yellow]开始初始化程序...')
        # 用 tomllib 替代 ConfigParser 进行解析 20231207
        config_file = Path(config_path)
        with config_file.open("rb") as cf:
            config = tomllib.load(cf)
            
        self._inputDir = config['DEFAULT']['InputDir']
        self._outputDir = config['DEFAULT']['OutputDir']
        self._cacheDir = config['DEFAULT']['CacheDir']
        self._fileList = self._initPathObj(exclude=config['DEFAULT']['Exclude'])

    @property
    def inputDir(self) -> str:
        return self._inputDir

    @property
    def outputDir(self) -> str:
        return self._outputDir

    @property
    def cacheDir(self) -> str:
        return self._cacheDir

    @property
    def fileList(self) -> list:
        return self._fileList

    def print(self, s, overflow="fold"):
        self.console.print(s, overflow=overflow)

    def log(self, s: str, overflow="fold"):
        mtui.log(self.console, s, overflow=overflow)

    def repack(self, file):
        file_t = Path(file)
        comic_name: str = file_t.parents[0].name
        comic_src = self._loadZipImg(file_t)
        real_output_dir = Path(self.outputDir)
        if comic_name != Path(self.inputDir).stem:
            real_output_dir = real_output_dir / comic_name
        self._packFolder(comic_src, real_output_dir)

    # 初始化路径并复制目录结构
    def _initPathObj(
            self,
            exclude=None
    ) -> list:
        # 目录表格绘制
        if exclude is None:
            exclude = []
        self.print(
            mtui.PathTable(
                self.inputDir,
                self.outputDir,
                self.cacheDir
            )
        )
        # 文件列表抽取
        mfst.removeIfExists(self.cacheDir)
        mfst.removeIfExists(self.outputDir)
        filelist: list = mfst.copyDirStructExtToList(self.inputDir)
        self.log("[green]已完成文件列表抽取。")
        # 目录结构复制
        mfst.copyDirStruct(self.inputDir, self.outputDir, exclude=exclude)
        self.log("[green]已完成目录结构复制。")
        return filelist

    # HTML 按照 vol.opf 中规定的顺序抽取成列表
    # 本函数是为 Mox.moe 新发布的文件设计，但兼容老版本
    # 以解决新版本文件中网页顺序打乱导致图片顺序错乱问题
    def _htmlExtractToList(
            self,
            extract_dir: Path,
            soup: BeautifulSoup
    ) -> list:
        def _htmlObjExtract(
                curr_page: dict[str, Union[str, Any]],
                extract_dir: Path,
                length: int
        ) -> tuple:
            idx: str = curr_page['id'].replace('Page_', '')
            
            # idx 有三种可能取值：'cover', 全数字, 'createby'
            rename_idx_dict = {
                'cover': 0,
                'createby': length
            }
            rename_idx: int = rename_idx_dict.get(idx, int(idx) if idx.isnumeric() else length)
            
            file_stem: str = re.findall(r'[^/]+\.html', curr_page['href'])[0]
            raw_path = extract_dir / 'html' / file_stem
            
            return rename_idx, raw_path
        
        raw_pages = soup.package.manifest.find_all('item', {'media-type': 'application/xhtml+xml'})
        reduced_pages = sorted(
            map(
                lambda pg: _htmlObjExtract(pg, extract_dir, len(raw_pages)), 
                raw_pages
                ),
            key=lambda x: x[0]
        )
        return list(zip(*reduced_pages))[1]

    # 新的漫画名称抽取函数 20230528 函数已弃用 20231211
    @staticmethod
    def _comicNameExtract(soup: BeautifulSoup) -> str:
        author: str = soup.package.metadata.find('dc:creator').string
        title, volume = soup.package.metadata.find('dc:title').string.split(' - ')
        filename = mutl.sanitizeFileName(f'[{author}][{title}]{volume}')
        return filename

    # 单个压缩包根据HTML文件中的图片地址进行提取
    def _loadZipImg(self, zip_file) -> Path:
        def _getUniqueExtractDir():
            extract_dir = Path(self.cacheDir, str(zip_file.stem))
            while extract_dir.is_dir():
                extract_dir = Path(self.cacheDir, str(zip_file.stem) + '_dup')
            return extract_dir
        
        def _renameImage(html_file):
            soup = mutl.readHtmlFile(html_file)
            title: str = soup.title.string
            imgsrc = Path(soup.img['src'])
            imgsrc = img_dir / imgsrc.name
            new_name: str = ''
            
            if 'cover' in imgsrc.name:
                new_name = f'COVER{imgsrc.suffix}'
            # 鉴于新版 Kox.moe 电子书已不再设置 END 标记尾页，此分支弃用 20231207
            # elif 'END' in title:
            #     new_name = f'THE END{imgsrc.suffix}'
            else:
                page_num: str = re.search(r'\d+', title).group(0)
                new_name = f'PAGE{int(page_num):03}{imgsrc.suffix}'
            imgsrc.rename(Path(imgsrc.parent, new_name))
            
        def _organizeImages(img_dir: Path, comic_name: str) -> Path:
            img_dir = img_dir.rename(Path(img_dir.parent, comic_name))
            img_filelist = mfst.copyDirStructToList(str(img_dir))
            for file in img_filelist:
                imgfile = Path(file)
                imgstem = imgfile.stem
                if all(s not in imgstem for s in ['COVER', 'END', 'PAGE']):
                    imgfile.unlink()
            return img_dir
        
        self.log(f'[yellow]开始解析 {zip_file.stem}')
        
        # 避免相同文件名解压到缓存文件夹时冲突
        extract_dir = _getUniqueExtractDir()

        shutil.unpack_archive(str(zip_file), extract_dir=extract_dir, format="zip")
        opf_file = extract_dir / 'vol.opf'
        soup_0 = mutl.readXmlFile(opf_file)
        comic_name: str = mcif.ComicInfoExtractor(opf_file).comic_file_name
        self.log(f'{comic_name} => [yellow]开始提取')
        
        img_dir = extract_dir / 'image'
        html_list: list = self._htmlExtractToList(extract_dir, soup_0)

        for html_file in html_list:
            _renameImage(html_file)
        
        img_dir = _organizeImages(img_dir, comic_name)
        
        self.log(f'{comic_name} => [green]提取完成')
        return img_dir

    # 打包成压缩包并重命名
    # 用 shutil.make_archive() 代替 zipFile，压缩体积更小
    # 修改输出路径为绝对路径，避免多次切换工作目录 20230429
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=(stop_after_attempt(5) | stop_after_delay(1.5))
    )
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
