import re
from pathlib import Path
from typing import Iterable

from lxml import etree

from .utils import cn2an_simple, sanitize_filename

MoxBookType: list[str] = ["其他", "單行本", "番外篇", "連載話"]

all_volume_pattern: str = r"全[01234567890零一二三四五六七八九十百千萬億万亿壹貳叄肆伍陸柒捌玖拾佰仟贰叁陆]+[卷話冊]"


class MoxBook:
    """
    以下为 MOXBID 已经探明的规律：
    前 3 位：恒为 200
    4-8 位：bookid
    - bookid 为 5 位十进制数，str_bookid 为 6 位十六进制数，两者存在编解码关系
    - 打开书籍网址链接现行规范："/c/{str_bookid}.htm"
    - 获取书籍数据请求现行规范："/book_data.php?h={timestamp:10 位数字}1{str_bookid}{5 位数字, 可能与书籍属性相关}{uid:8 位数字}{6 位 16 进制整数, 功能尚不明确}"
    - 对于较早期的链接，str_bookid 就是 "X{bookid}"，其中字母 X 为占位符
    - 对于新创建的链接，str_bookid 经 bookid 编码得到
    9 位：分组
    - 1：单行本
    - 2：番外篇
    - 3：连载话
    10-12 位：分组中顺序
    - 作为连载话时存在歧义，可能为第几个文件，也可能为标注的起始话数
    13 位：疑似八进制数
    """

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

    @staticmethod
    def _full_count(vol: str) -> int:
        vol = vol.replace("全", "")
        for vol_mark in "卷話冊":
            if vol_mark in vol:
                vol = vol.replace(vol_mark, "")
        return cn2an_simple(vol)

    @staticmethod
    def _full_count_str(vol: str) -> str:
        return str(MoxBook._full_count(vol))

    @staticmethod
    def _volume_count(vol: str) -> int:
        return int(re.sub(r"卷(\d+).*", r"\1", vol))

    @staticmethod
    def _volume_count_str(vol: str) -> str:
        return vol.replace("卷", "")

    @staticmethod
    def _serial_count(vol: str) -> str:
        return vol.replace("話", "")

    @staticmethod
    def _serial_diff_count(vol: str) -> int:
        start, end = vol.replace("話", "").strip().split("-")
        return int(end) - int(start) + 1

    @property
    def number(self) -> str:
        pattern_actions = {
            r"卷\d+": MoxBook._volume_count_str,
            all_volume_pattern: MoxBook._full_count_str,
            r"話(\d+?-\d+)": MoxBook._serial_count,
        }

        for pattern, action in pattern_actions.items():
            if re.match(pattern, self.vol):
                return action(self.vol)

        return "1"

    @property
    def count(self) -> int:
        pattern_actions = {
            r"卷\d+": MoxBook._volume_count,
            all_volume_pattern: MoxBook._full_count,
            r"話(\d+?-\d+)": MoxBook._serial_diff_count,
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
            info_data: dict = etree.fromstring(input_data, parser=etree.XMLParser())
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
        return str(self._metadata["MOXBID"])

    def __str__(self):
        return self.to_xml().decode(encoding="utf-8")

    def to_dict(self) -> dict[str, str | int]:
        return self._metadata

    def to_xml(self) -> bytes:
        data = self.to_dict()
        root = etree.Element("ComicInfo", attrib=None, nsmap=None)
        self._build_xml(root, data)
        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="utf-8"
        )

    def to_xml_file(self, output: Path) -> None:
        with output.open("w", encoding="utf-8") as of:
            of.write(self.to_xml().decode("utf-8"))

    def _build_xml(self, parent: etree._Element, data: dict):
        for key, value in data.items():
            if isinstance(value, dict):
                element = etree.Element(key, attrib=None, nsmap=None)
                parent.append(element)
                self._build_xml(element, value)
            elif isinstance(value, list):
                for item in value:
                    element = etree.Element(key, attrib=None, nsmap=None)
                    parent.append(element)
                    self._build_xml(element, item)
            else:
                element = etree.Element(key, attrib=None, nsmap=None)
                element.text = str(value)
                parent.append(element)


class ComicInfoExtractor:
    _metadata: str
    _package: etree.Element
    _mox_book: MoxBook
    _comic_data: dict[str, str | int]
    ns: dict[str, str]

    def __init__(
        self, use_text: bool = True, opf_text: str = "", opf_file: Path | None = None
    ):
        # 设定命名空间
        self.ns = {
            "dc": "http://purl.org/dc/elements/1.1/",
            "opf": "http://www.idpf.org/2007/opf",
        }

        # 解析元数据
        if use_text:
            self._load_opf_text(opf_text)
        else:
            assert opf_file is not None
            self._load_opf_file(opf_file)

        self._package = etree.fromstring(
            self._metadata.encode("utf-8"), parser=etree.XMLParser()
        )

        self._comic_data = {}
        self._comic_data["Publisher"] = "Kox.moe"
        self._comic_data["Manga"] = "Yes"

        self._build_mox_book()
        self._build_comic_info()

    def _load_opf_text(self, opf_text: str):
        self._metadata = opf_text

    def _load_opf_file(self, opf_file: Path):
        with opf_file.open("r", encoding="utf-8") as opff:
            self._metadata = opff.read()

    # 安全搜索，避免返回空列表引发错误
    def _get_xpath_text(self, xpath: str) -> str:
        res: str = ""
        res_finder = self._package.xpath(xpath, namespaces=self.ns)
        if res_finder:
            res = res_finder[0].text
        return res

    def _build_mox_book(self):
        moxbid: str = self._get_xpath_text('.//dc:identifier[@id="MOXBID"]')
        title: str = self._get_xpath_text(".//dc:title")
        volume = title.split(" - ")[-1].strip()
        self._mox_book = MoxBook(moxbid, volume)
        self._comic_data["MOXBID"] = moxbid
        self._comic_data["Title"] = title
        self._comic_data["Volume"] = volume
        self._comic_data["Number"] = self.mox_book.number
        self._comic_data["Count"] = self.mox_book.count
        self._comic_data["Web"] = self.mox_book.weburl

    def _build_comic_info(self):
        self._comic_data["Series"] = self._get_xpath_text(".//dc:series")
        self._comic_data["Writer"] = self._get_xpath_text(".//dc:creator")
        self._comic_data["Publisher"] = self._get_xpath_text(".//dc:publisher")
        self._comic_data["Year"] = self._get_xpath_text(".//dc:date")
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
        return sanitize_filename(f"[{author}][{series}]{volume}")

    @property
    def comic_page_count(self) -> int:
        return int(self._comic_data["PageCount"])

    def _build_filelist(self, xpath: str) -> Iterable[tuple[str, str]]:
        # 返回一个迭代器，元素格式为元组 (id, href)
        return map(
            lambda x: (x.attrib["id"], x.attrib["href"]),
            self._package.xpath(
                xpath,
                namespaces=self.ns,
            ),
        )

    def _build_html_filelist(self, extract_dir: Path) -> Iterable[tuple[str, Path]]:
        file_list = self._build_filelist(
            xpath='.//opf:manifest/opf:item[@media-type="application/xhtml+xml"]'
        )
        return map(lambda x: (x[0], extract_dir / x[1]), file_list)

    def _build_img_filelist(self, extract_dir: Path) -> Iterable[tuple[str, Path]]:
        # 实际上 PNG 图片仅有版权页和备用封面页，保留相关 xpath 供查询调试
        file_list = self._build_filelist(
            xpath='.//opf:manifest/opf:item[@media-type="image/jpeg"]'
            # xpath='.//opf:manifest/opf:item[@media-type="image/jpeg"] | .//opf:manifest/opf:item[@media-type="image/png"]'
        )
        return map(lambda x: (x[0], extract_dir / x[1]), file_list)

    def build_img_filelist(
        self, extract_dir: Path, direct: bool = False
    ) -> Iterable[tuple[str, Path]]:
        # 提供两种方式：间接从网页内容获取图片地址，以及直接从 vol.opf 文件获取图片地址
        # 设置两种方式主要是防止其中一种顺序出现错误，但暂不提供接口
        # 但是直接获取图片并不能保证其顺序正确，因此还是使用网页列表对图片排序
        img_list = []

        def _rename_idx(idx: str, length: int) -> int:
            if idx.isnumeric():
                return int(idx)
            elif idx == "cover":
                return 0
            else:
                return length

        def _rename_img_idx(renamed_idx: int) -> str:
            if renamed_idx == 0:
                return "COVER"
            else:
                return f"PAGE{renamed_idx:03}"

        def _extract_img_from_html(html_path: Path) -> Path:
            with html_path.open("r", encoding="utf-8") as hf:
                html_text = hf.read()
                html_tree: etree.Element = etree.fromstring(
                    html_text, parser=etree.HTMLParser()
                )
                return (
                    extract_dir / html_tree.xpath(".//img[@src]")[0].attrib["src"][3:]
                )

        if not direct:
            for html_title, html_path in self._build_html_filelist(extract_dir):
                idx: str = html_title.replace("Page_", "")
                renamed_idx: int = _rename_idx(idx, self.comic_page_count)
                new_name = _rename_img_idx(renamed_idx)
                img_src = _extract_img_from_html(html_path)
                img_list.append((new_name, img_src))
        else:
            # 以下如非调试不考虑正式使用
            for img_title, img_path in self._build_img_filelist(extract_dir):
                idx: str = img_title.replace("img", "").replace("_", "")
                renamed_idx = _rename_idx(idx, self.comic_page_count)
                new_name = _rename_img_idx(renamed_idx)
                img_list.append((new_name, img_path))

        return img_list
