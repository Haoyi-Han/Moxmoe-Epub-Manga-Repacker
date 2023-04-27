import os
import pathlib
import shutil

# 在指定目录下复制空目录结构
def copyDirStruct(inPath: str, outPath: str, ifinclude: bool=True, exclude: list[str]=[]):
    exclude.append(outPath)
    shutil.copytree(inPath, outPath, ignore=lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))] + exclude)

# 创建文件列表（按原目录结构）    
def copyDirStructToList(root: str) -> list:
    return [pathlib.Path(os.path.join(path, name)) for path, subdirs, files in os.walk(root) for name in files]

# 创建EPUB文件列表（按原目录结构）
def copyDirStructExtToList(root: str, ext='.epub') -> list:
    filelist: list = copyDirStructToList(root)
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

def removeIfExists(path):
    if path.is_dir():
        shutil.rmtree(os.fspath(path), ignore_errors=True)