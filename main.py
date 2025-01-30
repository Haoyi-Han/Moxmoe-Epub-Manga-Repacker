# 主程序引用库
import os
from contextlib import AbstractContextManager
from typing import Annotated

# 程序命令行帮助美化
import typer

# 程序显示引用库
from rich.console import Console, OverflowMethod
from rich.progress import Progress, TaskID
from rich.prompt import Prompt

# 程序异常打印库
from rich.traceback import install

from moe_utils.file_system import remove_if_exists
from moe_utils.manga_repacker import ComicFile, Repacker
from moe_utils.progress_bar import generate_progress_bar
from moe_utils.taskbar_indicator import WinTaskbar, create_wintaskbar_object
from moe_utils.terminal_ui import log as tui_log
from moe_utils.terminal_ui import welcome_panel

install(show_locals=True)

##############################

typer_app = typer.Typer(no_args_is_help=True)


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
        if self.tb_imported:
            self.tb.set_taskbar_progress(i, self.total)


@typer_app.command(help="List manga files without executing the conversion")
def list(
    config: Annotated[str, typer.Argument(..., help="Config file path")] = "config.toml",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--no-verbose",
            "-v/-V",
            help="Enable/Disable verbose output during the application execution",
            rich_help_panel="Override Options",
        ),
    ] = False,
):
    console = Console()
    repacker = Repacker(verbose=verbose, console=console)
    repacker.init_data(config_path=config)
    repacker.print_list()


# 采用 rich.progress 实现进度条效果
# 引入 CPU 线程池，提高任务执行效率 20230429
# 更改 CPU 线程池为 CPU 进程池 20230521
# 弃用多进程/多线程，改用异步 20230525
# 移除所有多进程/多线程/协程模块 20230528
# 使用上下文管理器进行封装 20231228
# 主进程完全重构 20240201
# 使用 typer 重构交互功能 20250128
@typer_app.command(help="Convert manga files with specified options")
def convert(
    config: Annotated[str, typer.Argument(..., help="Config file path")] = "config.toml",
    taskbar: Annotated[
        bool,
        typer.Option(
            "--taskbar/--no-taskbar",
            "-t/-T",
            help="Enable/Disable Taskbar Progress Display",
            rich_help_panel="Override Options",
        ),
    ] = True,
    logo: Annotated[
        bool,
        typer.Option(
            "--logo/--no-logo",
            "-g/-G",
            help="Enable/Disable logo display when the application starts",
            rich_help_panel="Override Options",
        ),
    ] = True,
    progress: Annotated[
        bool,
        typer.Option(
            "--progress/--no-progress",
            "-p/-P",
            help="Enable/Disable progress bar display during the conversion",
            rich_help_panel="Override Options",
        ),
    ] = True,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--no-verbose",
            "-v/-V",
            help="Enable/Disable verbose output during the application execution",
            rich_help_panel="Override Options",
        ),
    ] = True,
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet/--no-quiet",
            "-q/-Q",
            help="Enable/Disable silent mode during the conversion",
            rich_help_panel="Override Options",
        ),
    ] = False,
    keep_cache: Annotated[
        bool,
        typer.Option(
            "--keep-cache/--no-keep-cache",
            "-k/-K",
            help="Enable/Disable keeping cache folder when the application exits",
            rich_help_panel="Override Options",
        ),
    ] = False,
):
    if quiet:
        logo = False
        progress = False
        taskbar = False
        verbose = False

    pb = generate_progress_bar()
    console = pb.console
    win_tb: WinTaskbar | None = None

    def tprint(s, *, overflow: OverflowMethod = "fold"):
        console.print(s, overflow=overflow)

    def tlog(s: str, *, overflow: str = "fold", verbose: bool = True):
        if verbose:
            tui_log(console, s, overflow=overflow)

    # 键盘Ctrl+C中断命令优化
    def keyboard_handler(signum, frame):
        try:
            # 重置进度条
            pb.stop()
            if win_tb is not None:
                win_tb.reset_taskbar_progress()

            # 选择是否保留已转换文件和缓存文件夹
            console.print("[yellow]您手动中断了程序。")
            resp_out = Prompt.ask("请选择是否保留已转换文件", choices=["y", "n"], default="y")
            resp_cache = Prompt.ask("请选择是否保留缓存文件夹", choices=["y", "n"], default="n")
            # 除打包阶段使用的当前电子书文件外，其他文件均可清除
            # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
            if resp_out == "n":
                os.chdir(repacker.input_dir)  # 防止进程占用输出文件夹 20230429
                remove_if_exists(repacker.output_dir, recreate=True)
            if resp_cache != "y":
                os.chdir(repacker.input_dir)  # 防止进程占用缓存文件夹 20230429
                remove_if_exists(repacker.cache_dir)
        finally:
            exit(0)

    # 将主要执行过程封装，用于单线程或多线程时调用 20230429
    # 将执行过程提取到主函数外部 20230521
    def work(file_t: ComicFile):
        repacker.repack(file_t)

    def _convert() -> bool:
        if not progress:
            for i, file_t in enumerate(repacker.filelist):
                work(file_t)
        else:
            with ProgressController(
                pb=pb,
                tb=win_tb,
                description="Kmoe",
                total=len(repacker.filelist),
            ) as pctrl:
                pctrl: ProgressController
                for i, file_t in enumerate(repacker.filelist):
                    work(file_t)
                    pctrl.update(i)

        if repacker.faillist:
            tprint("[yellow]提示：以下文件转换失败！")
            indent: str = " " * 11
            for file_t in repacker.faillist:
                tprint(f"{indent}{file_t.relative_path}")
            return True

        return False

    # 优化键盘中断命令
    import signal

    signal.signal(signal.SIGINT, keyboard_handler)
    signal.signal(signal.SIGTERM, keyboard_handler)

    # 欢迎界面
    if logo:
        tprint(welcome_panel)

    # 初始化转换器对象
    tlog("[yellow]开始初始化程序...")
    repacker = Repacker(verbose=verbose, console=console)
    repacker.init_data(config_path=config)

    if taskbar:
        win_tb = create_wintaskbar_object()

    tlog("[yellow]开始提取图片并打包文件...")

    pause = _convert()

    if not keep_cache:
        tlog("[yellow]开始清理缓存文件...", verbose=verbose)
        repacker.clean_cache()

    tlog("[green]所有转换任务完成！")

    if pause:
        input("请按任意键继续...")


@typer_app.command(help="Clean cache and/or output files")
def clean(
    config: Annotated[str, typer.Argument(..., help="Config file path")] = "config.toml",
    cache: Annotated[bool, typer.Option("--cache", "-c", help="Clean cache files")] = False,
    input: Annotated[bool, typer.Option("--input", "-i", help="Clean input files")] = False,
    output: Annotated[bool, typer.Option("--output", "-o", help="Clean output files")] = False,
    all: Annotated[bool, typer.Option("--all", "-a", help="Clean all files, including cache and output")] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose/--no-verbose",
            "-v/-V",
            help="Enable/Disable verbose output during the application execution",
            rich_help_panel="Override Options",
        ),
    ] = True,
):
    def tlog(s: str, *, overflow: str = "fold", verbose: bool = True):
        if verbose:
            tui_log(console, s, overflow=overflow)

    console = Console()
    repacker = Repacker(verbose=verbose, console=console)
    repacker.init_data(config_path=config, init_filelist_flag=False)

    if all:
        cache = True
        output = True
    if cache:
        tlog("[yellow]开始清理缓存文件...", verbose=verbose)
        repacker.clean_cache()
    if input:
        tlog("[yellow]开始清理输入文件...", verbose=verbose)
        repacker.clean_input()
    if output:
        tlog("[yellow]开始清理输出文件...", verbose=verbose)
        repacker.clean_output()


@typer_app.command(help="Display the version information of the application")
def version():
    author = "Haoyi HAN"
    version = "0.6.1"
    year = 2025
    print(f"moxmoe repacker v{version}, by {author}, {year}")


if __name__ == "__main__":
    typer_app()
