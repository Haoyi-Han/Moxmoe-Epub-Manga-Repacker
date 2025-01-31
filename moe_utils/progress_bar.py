from contextlib import AbstractContextManager

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text

from moe_utils.taskbar_indicator import WinTaskbar


# 进度条外观设计
class NaiveTransferSpeedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text("?", style="progress.data.speed")
        return Text(f"({speed:>.2f}/s)", style="progress.data.speed")


def generate_progress_bar(console: Console):
    return Progress(
        TextColumn("[green]{task.description}"),
        SpinnerColumn(),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[green][{task.percentage:>3.1f}%]"),
        NaiveTransferSpeedColumn(),
        "ETD:",
        TimeElapsedColumn(),
        "ETA:",
        TimeRemainingColumn(),
        auto_refresh=False,
        console=console,
        transient=False,
    )


# 使用上下文管理器进行封装 20231228
class ProgressController(AbstractContextManager):
    pb: Progress
    tb: WinTaskbar | None = None
    tb_imported: bool = False
    description: str
    total: int
    task: TaskID

    def __init__(self, pb: Progress, tb: WinTaskbar | None, description: str, total: int):
        super().__init__()
        self.pb = pb
        self.tb = tb
        self.tb_imported = isinstance(tb, WinTaskbar)
        self.description = description
        self.total = total

    def __enter__(self):
        self.pb.start()
        self.task = self.pb.add_task(description=self.description, total=self.total)
        return super().__enter__()

    def __exit__(self, *exc_details):
        self.pb.stop()
        if self.tb_imported:
            self.tb.reset_taskbar_progress()

    def update(self, i: int):
        self.pb.update(self.task, advance=1)
        self.pb.refresh()
        if self.tb_imported:
            self.tb.set_taskbar_progress(i, self.total)
