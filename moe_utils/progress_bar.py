from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text


# 进度条外观设计
class NaiveTransferSpeedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.finished_speed or task.speed
        if speed is None:
            return Text("?", style="progress.data.speed")
        return Text(f"({speed:>.2f}/s)", style="progress.data.speed")


def generate_progress_bar():
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
        auto_refresh=True,
    )
