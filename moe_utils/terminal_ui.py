from rich.box import DOUBLE
from rich.panel import Panel
from rich.table import Table

from .utils import curr_time_format

welcome_panel = Panel.fit(
    "[bold cyan]支持 [green][link=https://vol.moe]Vol.moe[/link][/] & [green][link=https://mox.moe]Mox.moe[/link][/] & "
    "[green][link=https://kox.moe]Kox.moe[/link][/] 下载的漫画文件转换。[/] ",
    box=DOUBLE,
    title=" [bold green]Mox.moe EPUB Manga Repacker[/] ",
    border_style="cyan",
    padding=(1, 4),
)

welcome_logo: str = r"""
  __  __                                ____                       _             
 |  \/  | _____  ___ __ ___   ___   ___|  _ \ ___ _ __   __ _  ___| | _____ _ __ 
 | |\/| |/ _ \ \/ / '_ ` _ \ / _ \ / _ \ |_) / _ \ '_ \ / _` |/ __| |/ / _ \ '__|
 | |  | | (_) >  <| | | | | | (_) |  __/  _ <  __/ |_) | (_| | (__|   <  __/ |   
 |_|  |_|\___/_/\_\_| |_| |_|\___/ \___|_| \_\___| .__/ \__,_|\___|_|\_\___|_|   
                                                 |_|                             
"""


class PathTable(Table):
    def __init__(self, input_dir: str, output_dir: str, cache_dir: str):
        super().__init__(show_header=True, header_style="bold yellow")
        self.add_column("目录类型")
        self.add_column("目录路径")
        self.add_row("[cyan]输入目录", input_dir)
        self.add_row("[cyan]输出目录", output_dir)
        self.add_row("[cyan]缓存目录", cache_dir)


def log(console, s: str, overflow="fold"):
    console.print(f"[blue][{curr_time_format()}][/] {s}", overflow=overflow)
