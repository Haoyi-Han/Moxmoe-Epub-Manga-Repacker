import os
import shutil
import zipfile
from pathlib import Path


# 在指定目录下复制空目录结构
# 使用 shutil.ignore_patterns() 代替自定义排除函数 20230429
def copy_dir_struct(inPath: str, outPath: str, exclude=None):
    if exclude is None:
        exclude = []
    exclude.append(outPath)
    shutil.copytree(
        inPath,
        outPath,
        # ignore=lambda dir, files: [f for f in files if os.path.isfile(os.path.join(dir, f))] + exclude,
        ignore=shutil.ignore_patterns(*exclude, "*.*"),
        dirs_exist_ok=True,
    )


# 创建文件列表（按原目录结构）
def copy_dir_struct_to_list(root: str) -> list[Path]:
    return [
        Path(path, name)
        for path, subdirs, files in os.walk(root)
        for name in files
    ]


# 创建EPUB文件列表（按原目录结构）
def copy_dir_struct_ext_to_list(root: str, ext=".epub") -> list[Path]:
    filelist: list[Path] = copy_dir_struct_to_list(root)
    return [
        p
        for p in filelist
        if (not p.stem.startswith("._")) and (p.suffix == ext)
    ]


# 修改EPUB扩展名为ZIP
# 调整shutil.unpack_archive()参数后，解压不再需要依赖扩展名，本函数弃用
def suffix_change(filelist: list[Path], inType: str = ".epub", outType: str = ".zip") -> list:
    for i, filepath in enumerate(filelist):
        if filepath.suffix == inType:
            filepath = filepath.rename(filepath.with_suffix(outType))
        filelist[i] = filepath
    return filelist


def remove_if_exists(path: str):
    if Path(path).is_dir():
        shutil.rmtree(os.fspath(path), ignore_errors=True)


# shutil.make_archive() 不是线程安全的，因此考虑用以下函数代替
# https://stackoverflow.com/questions/41625702/is-shutil-make-archive-thread-safe
def make_archive_threadsafe(zip_name: str, path: str):
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for root, dirs, files in os.walk(path):
            for file in files:
                zip_f.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), path),
                )
