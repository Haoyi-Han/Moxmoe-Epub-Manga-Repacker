import os, shutil, pathlib, re
from bs4 import BeautifulSoup
import signal
import configparser as cp
from rich.progress import Progress, Task, Text, ProgressColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn, TimeRemainingColumn

# 进度条外观设计
class NaiveTransferSpeedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text("?", style="progress.data.speed")
        return Text(f"({speed:>.2f}/s)", style="progress.data.speed")

progress = Progress(
    TextColumn('[green]{task.description}'),
    BarColumn(),
    MofNCompleteColumn(),
    TextColumn('[green][{task.percentage:>3.1f}%]'),
    NaiveTransferSpeedColumn(),
    'ETD:',
    TimeElapsedColumn(),
    'ETA:',
    TimeRemainingColumn(),
    auto_refresh=True
)

class MoeUtils:
    # 键盘Ctrl+C中断命令优化（暂时用不到）
    def keyboardHandler(signum, frame):
        print(f'\033[93m您手动中断了程序，已经转换的文件和缓存文件夹将保留。\033[0m')
        exit()

    # 在指定目录下复制空目录结构
    def copyDirStruct(inPath: str, outPath: str, ifinclude: bool=True, exclude: list[str]=[]):
        if ifinclude:
            ignore_files = lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))] + [os.path.split(outPath)[1]] + exclude
        else:
            ignore_files = lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))] + exclude
        shutil.copytree(inPath, outPath, ignore=ignore_files)

    # 创建文件列表（按原目录结构）    
    def copyDirStructToList(root: str) -> list:
        return [pathlib.Path(os.path.join(path, name)) for path, subdirs, files in os.walk(root) for name in files]

    # 创建EPUB文件列表（按原目录结构）
    def copyDirStructExtToList(root: str, ext='.epub') -> list:
        filelist: list = MoeUtils.copyDirStructToList(root)
        return [p for p in filelist if (not p.stem.startswith('._')) and (p.suffix==ext)]
        
    # 修改EPUB扩展名为ZIP
    # 调整shutil.unpack_archive()参数后，解压不再需要依赖扩展名，本函数弃用
    def suffixChange(filelist: list, inType: str='.epub', outType: str='.zip') -> list:
        for i in range(len(filelist)):
            filepath = filelist[i]
            if filepath.suffix == inType:
                filepath = filepath.rename(filepath.with_suffix(outType))
            filelist[i] = filepath
        return filelist

    # 漫画名称抽取
    def comicNameExtract(comic_file) -> str:
        return re.search(r'^(\[.+?\])(.+?)\.+?', str(comic_file.stem)).group(2)

# 初始化路径并复制目录结构
def initPathObj(output_folder_name: str, exclude: list[str]=[]) -> tuple:
    curr_path = pathlib.Path(os.getcwd())
    cachefolder = curr_path / 'cache'
    if cachefolder.is_dir():
        shutil.rmtree(str(cachefolder))
    curr_filelist: list = MoeUtils.copyDirStructExtToList(str(curr_path))
    print("已完成文件列表抽取。")
    output_path = curr_path / 'output'
    if output_path.is_dir():
        shutil.rmtree(str(output_path))
    print("输入目录为：", curr_path)
    print("输出目录为：", output_path)
    MoeUtils.copyDirStruct(str(curr_path), str(output_path), ifinclude=(curr_path in output_path.parents), exclude=exclude)
    print("已完成目录结构复制。")
    return curr_path, output_path, curr_filelist

# HTML 按照 vol.opf 中规定的顺序抽取成列表
# 本函数是为 Mox.moe 新发布的文件设计，但兼容老版本
# 以解决新版本文件中网页顺序打乱导致图片顺序错乱问题
def htmlExtractToList(extract_dir):
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
def loadZipImg(zip_file, cachefolder):
    print("开始解析 ", zip_file.stem)
    # 避免相同文件名解压到缓存文件夹时冲突
    extract_dir = cachefolder / str(zip_file.stem)
    while extract_dir.is_dir():
        extract_dir = cachefolder / (str(zip_file.stem) + '_dup')
    comic_name: str = MoeUtils.comicNameExtract(zip_file)
    print(f'{comic_name} => 开始提取')
    shutil.unpack_archive(str(zip_file), extract_dir=extract_dir, format="zip")
    html_dir = extract_dir / 'html'
    img_dir = extract_dir / 'image'
    html_list: list = htmlExtractToList(extract_dir)
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
    img_filelist = MoeUtils.copyDirStructToList(str(img_dir))
    for imgfile in img_filelist:
        imgstem = imgfile.stem
        if all(s not in imgstem for s in ['COVER', 'END', 'PAGE']):
            imgfile.unlink()
    print(f'{comic_name} => 提取完成')
    return img_dir

# 打包成压缩包并重命名
# 用 shutil.make_archive() 代替 zipFile，压缩体积更小
def packFolder(inDir: str, outDir: str, ext: str='.cbz'):
    comic_name: str = inDir.name
    print(f'{comic_name} => 开始打包')
    zip_path = pathlib.Path(outDir, comic_name + '.zip')
    curr_path = os.getcwd()
    os.chdir(str(outDir))
    shutil.make_archive(comic_name, format='zip', root_dir=inDir)
    cbz_path = zip_path.rename(zip_path.with_suffix(ext))
    os.chdir(curr_path)
    print(f'{comic_name} => 打包完成')
    return cbz_path

# 主程序
if __name__ == '__main__':
    # 优化键盘中断命令（备用）
    signal.signal(signal.SIGINT, MoeUtils.keyboardHandler)
    signal.signal(signal.SIGTERM, MoeUtils.keyboardHandler)
    
    print('============> 开始初始化程序')
    config = cp.ConfigParser()
    config.read('./config.conf')
    curr_path, output_path, curr_filelist = initPathObj(
        config['DEFAULT']['OutputDir'],
        exclude=config['DEFAULT']['Exclude'].split('||')
        )
    cachefolder = curr_path / 'cache'
    
    print('============> 开始提取图片并打包文件')
    # 进度条效果
    # 用 rich.progress 代替 alive_progress，代码更简，外观更美观
    progress.start()
    task = progress.add_task(description='Kox.moe', total=len(curr_filelist))
    for file_t in curr_filelist:
        comic_name: str = file_t.parents[0].name
        comic_src = loadZipImg(file_t, cachefolder=cachefolder)
        if comic_name == curr_path.stem:
            packFolder(comic_src, output_path)
        else:
            packFolder(comic_src, output_path / comic_name)
        progress.update(task, advance=1)
    progress.stop()

    print('============> 开始清理缓存文件')
    shutil.rmtree(str(cachefolder))
    
    print('============> 完成')
