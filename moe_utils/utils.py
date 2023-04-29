import datetime
import os, stat
import re
    
# 系统当前时间格式化
def currTimeFormat():
    return datetime.datetime.now().strftime('%H:%M:%S')

# 漫画名称抽取
def comicNameExtract(comic_file) -> str:
    return re.search(r'^(\[.+?\])(.+?)\.+?', str(comic_file.stem)).group(2)

# 清除文件只读属性并重试回调函数
# https://docs.python.org/zh-cn/3/library/shutil.html#rmtree-example
def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
    finally:
        func(path)
    