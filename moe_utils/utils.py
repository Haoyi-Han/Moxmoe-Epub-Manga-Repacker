import datetime
import re
    
# 系统当前时间格式化
def currTimeFormat():
    return datetime.datetime.now().strftime('%H:%M:%S')

# 漫画名称抽取
def comicNameExtract(comic_file) -> str:
    return re.search(r'^(\[.+?\])(.+?)\.+?', str(comic_file.stem)).group(2)