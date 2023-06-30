import datetime
import os
import re
import stat
from pathlib import Path

from bs4 import BeautifulSoup


# 系统当前时间格式化
def currTimeFormat():
    return datetime.datetime.now().strftime('%H:%M:%S')


# 漫画名称抽取 函数已弃用 20230528
def comicNameExtract(comic_file) -> str:
    return re.search(r'^(\[.+?])(.+?)\.+?', str(comic_file.stem)).group(2)


# 清除文件只读属性并重试回调函数
# https://docs.python.org/zh-cn/3/library/shutil.html#rmtree-example
def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
    finally:
        func(path)


# 读取 XML 文件并返回 BeautifulSoup 类型
def readXmlFile(xml_file: Path):
    with xml_file.open('r', encoding='utf-8') as xf:
        soup_0 = BeautifulSoup(xf.read(), features='xml')
        return soup_0


# 读取 HTML 文件并返回 BeautifulSoup 类型
def readHtmlFile(html_file: Path):
    with html_file.open('r', encoding='utf-8') as hf:
        soup_0 = BeautifulSoup(hf.read(), 'html.parser')
        return soup_0


# 检查文件名是否合法，并处理其中的非法字符 20230630
def sanitizeFileName(filename: str) -> str:
    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    replacement_dict = {'/': '／', '\\': '＼', ':': '：', '*': '＊', '?': '？', '"': '＂', '<': '＜', '>': '＞', '|': '｜'}

    for char in invalid_chars:
        if char in filename:
            filename = filename.replace(char, replacement_dict.get(char, ''))

    return filename
