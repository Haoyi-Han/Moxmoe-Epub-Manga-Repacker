from rich.panel import Panel
from rich.box import DOUBLE

welcome_panel = Panel.fit(
                " [bold cyan]支持 [green][link=https://vol.moe]Vol.moe[/link][/] & [green][link=https://mox.moe]Mox.moe[/link][/] & [green][link=https://kox.moe]Kox.moe[/link][/] 下载的漫画文件转换。[/] ", 
                box=DOUBLE,
                title=" [bold green]Mox.moe EPUB Manga Repacker[/] ",
                border_style="cyan",
                padding=(1, 4)
                )