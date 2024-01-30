import os
import shutil
import time
import zipfile
from pathlib import Path

from rich.prompt import Prompt
import filedate


# 在指定目录下复制空目录结构
# 使用 shutil.ignore_patterns() 代替自定义排除函数 20230429
def copy_dir_struct(inPath: str, outPath: str, exclude=None):
    def ignore_files(dir: str, files: list[str]) -> list[str]:
        return [f for f in files if os.path.isfile(os.path.join(dir, f))]

    if exclude is None:
        exclude = []
    exclude.append(outPath)
    shutil.copytree(
        inPath,
        outPath,
        ignore=lambda dir, files: ignore_files(dir, files) + exclude,
        dirs_exist_ok=True,
    )


# 创建文件列表（按原目录结构）
# 使用 glob() 方法代替，本函数弃用
def copy_dir_struct_to_list(root: str) -> list[Path]:
    return [
        Path(path, name) for path, subdirs, files in os.walk(root) for name in files
    ]


# 创建EPUB文件列表（按原目录结构）
# 使用 glob() 方法重写
def copy_dir_struct_ext_to_list(root: str, ext=".epub") -> list[Path]:
    return list(
        filter(
            lambda path: not any((part for part in path.parts if part.startswith("."))),
            Path(root).rglob(f"*{ext}"),
        )
    )


# 修改EPUB扩展名为ZIP
# 调整shutil.unpack_archive()参数后，解压不再需要依赖扩展名，本函数弃用
def suffix_change(
    filelist: list[Path], inType: str = ".epub", outType: str = ".zip"
) -> list:
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
def make_archive_threadsafe(
    base_name: str | Path, format: str = "zip", root_dir: str | Path | None = None
):
    zip_name: str = f"{str(base_name)}.{format}"
    with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for root, dirs, files in os.walk(root_dir):
            for file in files:
                zip_f.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), root_dir),
                )


# shutil.unpack_archive() 解压时不保留文件时间戳，因此考虑用以下函数代替
# https://stackoverflow.com/questions/9813243/extract-files-from-zip-file-and-retain-mod-date
def unpack_archive_with_timestamp(
    filename: str | Path, extract_dir: str | Path | None = None
):
    with zipfile.ZipFile(str(filename), "r") as zip_ref:
        for member in zip_ref.infolist():
            member: zipfile.ZipInfo
            name, date_time = member.filename, member.date_time
            name = os.path.join(str(extract_dir), name)
            zip_ref.extract(member, extract_dir)
            date_time = time.mktime(date_time + (0, 0, -1))
            os.utime(name, (date_time, date_time))


# 检查字符串是否能够组成路径
def check_if_path_string_valid(
    path_string: str, check_only: bool = True, force_create: bool = False
) -> Path | None:
    try:
        if path_string is None:
            return None
        path = Path(path_string)
        if not path.exists():
            if check_only:
                print(f"警告：{path_string} 路径指向的文件夹不存在。")
                return None

            if not force_create:
                create_folder = Prompt.ask(
                    f"警告：{path_string} 路径指向的文件夹不存在，您想要创建吗？",
                    choices=["y", "n"],
                    default="n",
                )
                if create_folder == "y":
                    path.mkdir(parents=True, exist_ok=True)
                    return path
                else:
                    return None

            path.mkdir(parents=True, exist_ok=True)
            return path
        elif path.is_file():
            print("警告：该路径指向一个已存在的文件。")
            return None
        elif not os.access(path, os.R_OK):
            print("警告：该路径指向一个已存在的文件夹，但访问受限或被拒绝。")
            return None
        else:
            return path
    except Exception as e:
        print(f"警告：{e}")
        return None


# 复制文件时间戳信息
def copy_file_timestamp(
    src_file: str | Path,
    dst_file: str | Path,
    *,
    copy_ctime: bool = False,
    copy_mtime: bool = True,
    copy_atime: bool = True,
):
    filedate.copy(
        str(src_file),
        str(dst_file),
        created=copy_ctime,
        modified=copy_mtime,
        accessed=copy_atime,
    )
