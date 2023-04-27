import os, shutil, pathlib, re
from bs4 import BeautifulSoup
import moe_utils.progress_bar as mpbr
import moe_utils.file_system as mfst
import moe_utils.utils as mutl
from rich.table import Table

class Repacker:
    def __init__(self):
        self.progress = mpbr.generateProgressBar()

    # 初始化路径并复制目录结构
    def initPathObj(
        self,
        use_curr_as_input_dir: bool=True,
        input_dir: str='',
        create_output_folder_under_input_dir: bool=True,
        output_dir: str='',
        output_folder: str='output',
        exclude: list[str]=[]
        ) -> tuple:
        curr_path = pathlib.Path(os.getcwd() if use_curr_as_input_dir else input_dir)
        cachefolder = curr_path / 'cache'
        mfst.removeIfExists(cachefolder)
        curr_filelist: list = mfst.copyDirStructExtToList(str(curr_path))
        self.progress.console.print(f"[blue][{mutl.currTimeFormat()}][/] [green]已完成文件列表抽取。")
        output_path = curr_path / output_folder if create_output_folder_under_input_dir else pathlib.Path(output_dir)
        mfst.removeIfExists(output_path)
            
        # 目录表格绘制
        path_table = Table(show_header=True, header_style='bold yellow')
        path_table.add_column('目录类型')
        path_table.add_column('目录路径')
        path_table.add_row('[cyan]输入目录', str(curr_path))
        path_table.add_row('[cyan]输出目录', str(output_path))
        self.progress.console.print(path_table)

        mfst.copyDirStruct(str(curr_path), str(output_path), ifinclude=(curr_path in output_path.parents), exclude=exclude)
        self.progress.console.print(f"[blue][{mutl.currTimeFormat()}][/] [green]已完成目录结构复制。")
        return curr_path, output_path, curr_filelist

    # HTML 按照 vol.opf 中规定的顺序抽取成列表
    # 本函数是为 Mox.moe 新发布的文件设计，但兼容老版本
    # 以解决新版本文件中网页顺序打乱导致图片顺序错乱问题
    def htmlExtractToList(
        self, 
        extract_dir
        ) -> list:
        opf_file = extract_dir / 'vol.opf'
        with opf_file.open('r', encoding='utf-8') as volopf:
            soup_0 = BeautifulSoup(volopf.read(), features='xml')
        raw_pages = soup_0.package.manifest.find_all('item', {'media-type': 'application/xhtml+xml'})
        reduced_pages = []
        for raw_pg in raw_pages:
            raw_id = re.sub('Page_', '', raw_pg['id'])
            raw_file_stem = re.findall(r'[^/]+\.html', raw_pg['href'])[0]
            raw_path = extract_dir / 'html' / raw_file_stem        
            if 'cover' == raw_id:
                raw_id = 0
            elif raw_id.isnumeric():
                raw_id = int(raw_id)
            else:
                # 'createby' == raw_id
                raw_id = len(raw_pages)
            reduced_pages.append((raw_id, raw_path))
        reduced_pages.sort(key=lambda x: x[0])
        return list(zip(*reduced_pages))[1]

    # 单个压缩包根据HTML文件中的图片地址进行提取
    def loadZipImg(
        self, 
        zip_file, 
        cachefolder
        ):
        self.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] [yellow]开始解析 {zip_file.stem}')
        # 避免相同文件名解压到缓存文件夹时冲突
        extract_dir = cachefolder / str(zip_file.stem)
        while extract_dir.is_dir():
            extract_dir = cachefolder / (str(zip_file.stem) + '_dup')
        comic_name: str = mutl.comicNameExtract(zip_file)
        self.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] {comic_name} => [yellow]开始提取')
        shutil.unpack_archive(str(zip_file), extract_dir=extract_dir, format="zip")
        html_dir = extract_dir / 'html'
        img_dir = extract_dir / 'image'
        html_list: list = self.htmlExtractToList(extract_dir)
        for html_file in html_list:
            html_file_name: str = html_file.stem
            with html_file.open('r', encoding='utf-8') as hf:
                soup = BeautifulSoup(hf.read(), 'html.parser')
            title: str = soup.title.string
            imgsrc = pathlib.Path(soup.img['src'])
            imgsrc = img_dir / imgsrc.name
            if 'cover' in imgsrc.name:
                imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'COVER' + imgsrc.suffix))
            elif 'END' in title:
                imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'THE END' + imgsrc.suffix))
            else:
                page_num: str = re.search(r'\d+', title).group(0)
                imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'PAGE {:03}'.format(int(page_num)) + imgsrc.suffix))
        img_dir = img_dir.rename(pathlib.Path(img_dir.parent, comic_name))
        img_filelist = mfst.copyDirStructToList(str(img_dir))
        for imgfile in img_filelist:
            imgstem = imgfile.stem
            if all(s not in imgstem for s in ['COVER', 'END', 'PAGE']):
                imgfile.unlink()
        self.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] {comic_name} => [green]提取完成')
        return img_dir

    # 打包成压缩包并重命名
    # 用 shutil.make_archive() 代替 zipFile，压缩体积更小
    def packFolder(
        self, 
        inDir: str, 
        outDir: str, 
        ext: str='.cbz'
        ):
        comic_name: str = inDir.name
        self.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] {comic_name} => [yellow]开始打包')
        zip_path = pathlib.Path(outDir, comic_name + '.zip')
        curr_path = os.getcwd()
        os.chdir(str(outDir))
        shutil.make_archive(comic_name, format='zip', root_dir=inDir)
        cbz_path = zip_path.rename(zip_path.with_suffix(ext))
        os.chdir(curr_path)
        self.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] {comic_name} => [green]打包完成')
        return cbz_path