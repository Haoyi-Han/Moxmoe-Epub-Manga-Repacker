import re
from pathlib import Path

from lxml import etree

import moe_utils.utils as mutl

MoxBookType: list[str] = ["其他", "單行本", "番外篇", "連載話"]


class MoxBook:
    # 以下为 MOXBID 已经探明的规律：
    # 前 3 位：恒为 200
    # 4-8 位：ID
    # 9 位：分组
    # - 1：单行本
    # - 2：番外篇
    # - 3：连载话
    # 10-12 位：分组中顺序
    # - 作为连载话时存在歧义，可能为第几个文件，也可能为标注的起始话数
    # 13 位：疑似八进制数

    id: str
    volume: str

    def __init__(self, id: str | int, vol: str = ""):
        self.id = str(id)
        self.vol = vol

    @property
    def bookid(self) -> str:
        return self.id[3:8]

    @property
    def booktype(self) -> str:
        booktype_id: int = int(self.id[8])
        return MoxBookType[booktype_id if booktype_id < 4 else 0]

    @property
    def number(self) -> str:
        def full_count(vol: str) -> str:
            return str(mutl.cn2an_simple(vol.replace("全", "").replace("卷", "")))

        pattern_actions = {
            r"卷\d+": lambda x: x.replace("卷", ""),
            r"全[01234567890零一二三四五六七八九十百千萬億万亿壹貳叄肆伍陸柒捌玖拾佰仟贰叁陆]+卷": lambda x: full_count,
            r"話(\d+?-\d+)": lambda x: x.replace("話", ""),
        }

        for pattern, action in pattern_actions.items():
            if re.match(pattern, self.vol):
                return action(self.vol)

        return "1"

    @property
    def count(self) -> int:
        def full_count(vol: str) -> int:
            return mutl.cn2an_simple(vol.replace("全", "").replace("卷", ""))

        def serial_count(vol: str) -> int:
            start, end = vol.replace("話", "").strip().split("-")
            return int(end) - int(start) + 1

        pattern_actions = {
            r"卷\d+": lambda x: int(x.replace("卷", "")),
            r"全[01234567890零一二三四五六七八九十百千萬億万亿壹貳叄肆伍陸柒捌玖拾佰仟贰叁陆]+卷": full_count,
            r"話(\d+?-\d+)": serial_count,
        }

        for pattern, action in pattern_actions.items():
            if re.match(pattern, self.vol):
                return action(self.vol)

        return 1

    @property
    def weburl(self) -> str:
        # 早期漫画页面 ID 可直接对应 Kox.moe 网址，新版添加混淆后疑似采用六位 16 进制数加密 ID，尚不知具体算法
        # 不过新旧 ID 均可以通过 Bookof.moe 网址访问，因此暂时采用该地址作为 Web 标签内容
        return f"https://bookof.moe/b/{self.bookid}.htm"


class ComicInfo:
    _metadata: dict[str, str | int]

    def __init__(self, input_data: dict | str = {}):
        if isinstance(input_data, str):
            info_data: dict = etree.fromstring(input_data)
            info_data = info_data.get("ComicInfo", {})
        elif isinstance(input_data, dict):
            info_data: dict = input_data
        else:
            info_data: dict = {}

        self._metadata = {}

        self._metadata["MOXBID"] = info_data.get("MOXBID", "")
        self._metadata["Title"] = info_data.get("Title", "")
        self._metadata["Series"] = info_data.get("Series", "")
        self._metadata["Number"] = info_data.get("Number", 1)
        self._metadata["Count"] = info_data.get("Count", "")
        self._metadata["Volume"] = info_data.get("Volume", "")
        self._metadata["Summary"] = info_data.get("Summary", "")
        self._metadata["Writer"] = info_data.get("Writer", "")
        self._metadata["Publisher"] = info_data.get("Publisher", "Kox.moe")
        self._metadata["Year"] = info_data.get("Year", "2024")
        self._metadata["Web"] = info_data.get("Web", "")
        self._metadata["PageCount"] = info_data.get("PageCount", 0)
        self._metadata["Manga"] = info_data.get("Manga", "Yes")

    @property
    def id(self) -> str:
        return self._metadata["MOXBID"]

    def __str__(self):
        return self.to_xml().decode(encoding="utf-8")

    def to_dict(self) -> dict[str, str | int]:
        return self._metadata

    def to_xml(self) -> bytes:
        data = self.to_dict()
        root = etree.Element("ComicInfo")
        self._build_xml(root, data)
        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="utf-8"
        )

    def _build_xml(self, parent: etree.Element, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                element = etree.Element(key)
                parent.append(element)
                self._build_xml(element, value)
            elif isinstance(value, list):
                for item in value:
                    element = etree.Element(key)
                    parent.append(element)
                    self._build_xml(element, item)
            else:
                element = etree.Element(key)
                element.text = str(value)
                parent.append(element)


class ComicInfoExtractor:
    _metadata: str
    _package: etree.Element
    _mox_book: MoxBook
    _comic_data: dict[str, str | int]
    ns: dict[str, str]

    def __init__(self, opf_file: Path):
        # 设定命名空间
        self.ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "opf": "http://www.idpf.org/2007/opf",
        }

        # 解析元数据
        with opf_file.open("r", encoding="utf-8") as opff:
            self._metadata = opff.read()
            self._package = etree.fromstring(self._metadata.encode("utf-8"))

        self._comic_data = {}
        self._comic_data["Publisher"] = "Kox.moe"
        self._comic_data["Manga"] = "Yes"

        self.build_mox_book()
        self.build_comic_info()

    def build_mox_book(self):
        moxbid = self._package.xpath(
            './/dc:identifier[@id="MOXBID"]', namespaces=self.ns
        )[0].text
        title = self._package.xpath(".//dc:title", namespaces=self.ns)[0].text
        volume = title.split(" - ")[-1].strip()
        self._mox_book = MoxBook(moxbid, volume)
        self._comic_data["MOXBID"] = moxbid
        self._comic_data["Title"] = title
        self._comic_data["Volume"] = volume
        self._comic_data["Number"] = self.mox_book.number
        self._comic_data["Count"] = self.mox_book.count
        self._comic_data["Web"] = self.mox_book.weburl

    def build_comic_info(self):
        self._comic_data["Series"] = self._package.xpath(
            ".//dc:series", namespaces=self.ns
        )[0].text
        self._comic_data["Writer"] = self._package.xpath(
            ".//dc:creator", namespaces=self.ns
        )[0].text
        self._comic_data["Publisher"] = self._package.xpath(
            ".//dc:publisher", namespaces=self.ns
        )[0].text
        self._comic_data["Year"] = self._package.xpath(
            ".//dc:date", namespaces=self.ns
        )[0].text
        self._comic_data["PageCount"] = len(
            self._package.xpath(
                './/opf:spine[@toc="ncx"]/opf:itemref[@idref]', namespaces=self.ns
            )
        )

    @property
    def mox_book(self) -> MoxBook:
        return self._mox_book

    @property
    def comic_info(self) -> ComicInfo:
        return ComicInfo(self._comic_data)

    @property
    def comic_file_name(self) -> str:
        author = self._comic_data["Writer"]
        series = self._comic_data["Series"]
        volume = self._comic_data["Volume"]
        return mutl.sanitizeFileName(f"[{author}][{series}]{volume}")
