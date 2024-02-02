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


def remove_if_exists(path: str, *, recreate: bool = False):
    if Path(path).is_dir():
        shutil.rmtree(os.fspath(path), ignore_errors=True)
    if recreate:
        os.mkdir(path)


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
    filename: str | Path,
    extract_dir: str | Path | None = None,
    *,
    filters: list[str] | None = None,
):
    with zipfile.ZipFile(str(filename), "r") as zip_ref:
        filter_infolist: list[zipfile.ZipInfo] = zip_ref.infolist()
        if filters is not None:

            def check(p: zipfile.ZipInfo) -> bool:
                return any(p.filename.startswith(ft) for ft in filters)

            filter_infolist = list(filter(check, filter_infolist))

        for member in filter_infolist:
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


# 从文件列表打印目录树
# https://stackoverflow.com/questions/74056625/convert-list-of-path-like-strings-to-nested-dictionary-of-lists-arbitrary-depth
# https://stackoverflow.com/questions/72618673/list-directory-tree-structure-in-python-from-a-list-of-path-file
class PrettyDirectoryTree:
    # prefix components:
    space: str = "    "
    branch: str = "│   "
    # pointers:
    tee: str = "├── "
    last: str = "└── "

    _path_list: list[Path]
    _path_dict: dict

    def __init__(self, path_list: list[Path]):
        self._path_list = path_list
        self._parse_tree()
        self._print_tree()

    def _add_path(self, tree: dict, split_path: list[str]):
        subtree: dict = tree.setdefault(split_path[0], {})
        if len(split_path) > 1:
            self._add_path(subtree, split_path[1:])

    def _parse_tree(self):
        self._path_dict = {}
        for path in self._path_list:
            self._add_path(self._path_dict, list(path.parts))

    def _tree(self, paths: dict, prefix: str = "", first: bool = True):
        """A recursive generator, given a directory Path object
        will yield a visual tree structure line by line
        with each line prefixed by the same characters
        """
        # contents each get pointers that are ├── with a final └── :
        pointers = [self.tee] * (len(paths) - 1) + [self.last]
        for pointer, path in zip(pointers, paths):
            if first:
                yield prefix + f"\033[34m{path}\033[0m"
            else:
                yield prefix + pointer + f"\033[34m{path}\033[0m"
            if isinstance(paths[path], dict):  # extend the prefix and recurse:
                if first:
                    extension = ""
                else:
                    extension = self.branch if pointer == self.tee else self.space
                    # i.e. space because last, └── , above so no more │
                yield from self._tree(
                    paths[path], prefix=prefix + extension, first=False
                )

    def _print_tree(self):
        print()
        for line in self._tree(self._path_dict):
            print(line)
