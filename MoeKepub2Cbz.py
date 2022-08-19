import os, shutil, pathlib, zipfile, re
from bs4 import BeautifulSoup

# 在指定目录下复制空目录结构
def copyDirStruct(inPath, outPath, ifinclude=True):
    if ifinclude:
        ignore_files = lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))] + [os.path.split(outPath)[1]]
    else:
        ignore_files = lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))]
    shutil.copytree(inPath, outPath, ignore=ignore_files)

# 创建文件列表（按原目录结构）    
def copyDirStructToList(root):
    return [pathlib.Path(os.path.join(path, name)) for path, subdirs, files in os.walk(root) for name in files]

# 创建EPUB文件列表（按原目录结构）
def copyDirStructExtToList(root, ext='.epub'):
    filelist = copyDirStructToList(root)
    return [p for p in filelist if p.suffix==ext]

# 初始化路径并复制目录结构
def initPathObj(output_folder_name):
    curr_path = pathlib.Path(os.getcwd())
    curr_filelist = copyDirStructExtToList(str(curr_path))
    print("已完成文件列表抽取。")
    output_path = curr_path / 'output'
    if output_path.is_dir():
        shutil.rmtree(str(output_path))
    print("输入目录为：", curr_path)
    print("输出目录为：", output_path)
    copyDirStruct(str(curr_path), str(output_path), ifinclude=(curr_path in output_path.parents))
    print("已完成目录结构复制。")
    return curr_path, output_path, curr_filelist

# 修改EPUB扩展名为ZIP
def suffixChange(filelist, inType='.epub', outType='.zip'):
    for i in range(len(filelist)):
        filepath = filelist[i]
        if filepath.suffix == inType:
            filepath = filepath.rename(filepath.with_suffix(outType))
        filelist[i] = filepath
    return filelist

# 单个压缩包根据HTML文件中的图片地址进行提取
def loadZipImg(zip_file, cachefolder):
    print("开始解析 ", zip_file.stem)
    extract_dir = cachefolder / str(zip_file.stem)
    comic_name = re.search(r'moe](.+?)\.+?', str(zip_file.stem)).group(1)
    print("{} => 开始提取".format(comic_name))
    shutil.unpack_archive(str(zip_file), extract_dir=extract_dir)
    html_dir = extract_dir / 'html'
    img_dir = extract_dir / 'image'
    html_list = copyDirStructExtToList(str(html_dir), ext=".html")
    def checkIfHtmlFileNameLegal(name_str):
        if name_str.isnumeric(): return True
        else:
            name_str = name_str.lower()
            return (('cover.jpg' in name_str) or ('createby' in name_str))
    for html_file in html_list:
        html_file_name = html_file.stem
        if not checkIfHtmlFileNameLegal(html_file_name):
            continue
        with html_file.open('r', encoding='utf-8') as hf:
            soup = BeautifulSoup(hf.read(), 'html.parser')
        title = soup.title.string
        imgsrc = pathlib.Path(soup.img['src'])
        imgsrc = img_dir / imgsrc.name
        if 'cover' in imgsrc.name:
            imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'COVER' + imgsrc.suffix))
        elif 'END' in title:
            imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'THE END' + imgsrc.suffix))
        else:
            page_num = re.search(r'\d+', title).group(0)
            imgsrc = imgsrc.rename(pathlib.Path(imgsrc.parent, 'PAGE {:03}'.format(int(page_num)) + imgsrc.suffix))
    img_dir = img_dir.rename(pathlib.Path(img_dir.parent, comic_name))
    print("{} => 提取完成".format(comic_name))
    return img_dir

# 打包成压缩包并重命名
def packFolder(inDir, outDir, ext='.cbz'):
    comic_name = inDir.name
    print("{} => 开始打包".format(comic_name))
    outFile = pathlib.Path(outDir, comic_name + '.zip')
    with zipfile.ZipFile(str(outFile), mode='w') as archive:
        for file_path in inDir.iterdir():
            archive.write(file_path, arcname=file_path.name)
    outFile = outFile.rename(outFile.with_suffix(ext))
    print("{} => 打包完成".format(comic_name))
    return outFile

# 主程序
if __name__ == '__main__':
    curr_path, output_path, curr_filelist = initPathObj('output')
    print('============> 开始重命名文件')
    curr_filelist = suffixChange(curr_filelist)
    cachefolder = curr_path / 'cache'
    if cachefolder.is_dir():
        shutil.rmtree(str(cachefolder))
    print('============> 开始提取图片并打包文件')
    for file_t in curr_filelist:
        comic_name = file_t.parents[0].name
        comic_src = loadZipImg(file_t, cachefolder=cachefolder)
        packFolder(comic_src, output_path / comic_name)
    curr_filelist = suffixChange(curr_filelist, inType='.zip', outType='.epub')
    print('============> 开始清理缓存文件')
    shutil.rmtree(str(cachefolder))
    print('============> 完成')