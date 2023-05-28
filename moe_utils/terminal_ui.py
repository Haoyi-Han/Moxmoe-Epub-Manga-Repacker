from rich.box import DOUBLE
from rich.panel import Panel
from rich.table import Table

import moe_utils.utils as mutl

welcome_panel = Panel.fit(
    "[bold cyan]支持 [green][link=https://vol.moe]Vol.moe[/link][/] & [green][link=https://mox.moe]Mox.moe[/link][/] & "
    "[green][link=https://kox.moe]Kox.moe[/link][/] 下载的漫画文件转换。[/] ",
    box=DOUBLE,
    title=" [bold green]Mox.moe EPUB Manga Repacker[/] ",
    border_style="cyan",
    padding=(1, 4)
)


class PathTable(Table):
    def __init__(self, input_dir: str, output_dir: str, cache_dir: str):
        super().__init__(show_header=True, header_style='bold yellow')
        self.add_column('目录类型')
        self.add_column('目录路径')
        self.add_row('[cyan]输入目录', input_dir)
        self.add_row('[cyan]输出目录', output_dir)
        self.add_row('[cyan]缓存目录', cache_dir)


def log(console, s: str, overflow="fold"):
    console.print(f"[blue][{mutl.currTimeFormat()}][/] {s}", overflow=overflow)
