import datetime
import os
import stat

# from bs4 import BeautifulSoup


# 系统当前时间格式化
def currTimeFormat():
    return datetime.datetime.now().strftime("%H:%M:%S")


# 清除文件只读属性并重试回调函数
# https://docs.python.org/zh-cn/3/library/shutil.html#rmtree-example
def remove_readonly(func, path, _):
    try:
        os.chmod(path, stat.S_IWRITE)
    finally:
        func(path)


# 读取 XML 文件并返回 BeautifulSoup 类型
# def readXmlFile(xml_file: Path):
#     with xml_file.open("r", encoding="utf-8") as xf:
#         soup_0 = BeautifulSoup(xf.read(), features="xml")
#         return soup_0


# 读取 HTML 文件并返回 BeautifulSoup 类型
# def readHtmlFile(html_file: Path):
#     with html_file.open("r", encoding="utf-8") as hf:
#         soup_0 = BeautifulSoup(hf.read(), "html.parser")
#         return soup_0


# 检查文件名是否合法，并处理其中的非法字符 20230630
def sanitizeFileName(filename: str) -> str:
    invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
    replacement_dict = {
        "/": "／",
        "\\": "＼",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "＂",
        "<": "＜",
        ">": "＞",
        "|": "｜",
    }

    for char in invalid_chars:
        if char in filename:
            filename = filename.replace(char, replacement_dict.get(char, ""))

    return filename


# 三位数以内中文数字转换阿拉伯数字
def cn2an_simple(cn: str) -> int:
    chinese_to_arabic = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "百": 100,
    }

    result = 0
    temp = 0
    for key in cn:
        value = chinese_to_arabic.get(key, None)
        if value is None:
            return 1
        if value >= 10:
            if value > temp:
                result = (result + temp) * value
            else:
                result += temp * value
            temp = 0
        else:
            temp = value
    result += temp
    return result
