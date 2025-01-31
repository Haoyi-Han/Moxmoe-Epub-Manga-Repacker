# 主程序引用库
import inspect  # noqa: I001
import os
from collections import deque
from time import sleep
from typing import Annotated

# 程序命令行帮助美化
import typer
from typer.main import get_command_name

# 程序显示引用库
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

# 程序异常打印库
from rich.traceback import install

# 程序功能引用库
from moe_utils.file_system import remove_if_exists
from moe_utils.manga_repacker import ComicFile, Repacker
from moe_utils.progress_bar import ProgressController, generate_progress_bar
from moe_utils.taskbar_indicator import WinTaskbar, create_wintaskbar_object
from moe_utils.terminal_ui import DynamicLogger, tui_log, tui_print, welcome_logo, welcome_panel

install(show_locals=True)

##############################

cmd_help = {
    "list": "List manga files without executing the conversion",
    "convert": "Convert manga files with specified options",
    "clean": "Clean cache and/or output files",
    "version": "Display the version information of the application",
}


# 使用 class 封装 typer 应用 20250131
# https://github.com/fastapi/typer/issues/309
class Application:
    author: str = "Haoyi HAN"
    app_version: str = "0.6.2"
    year: int = 2025

    def __init__(self):
        self.typer_app = typer.Typer(no_args_is_help=True)
        self._init_cmd()

        self.console = Console()
        self.verbose = True

        self.dlogger = DynamicLogger(self.console)

    def _init_cmd(self):
        for method, func in inspect.getmembers(self, predicate=inspect.ismethod):
            if not method.startswith("cmd_"):
                continue

            command_name = get_command_name(method.removeprefix("cmd_"))
            self.typer_app.command(name=command_name, help=cmd_help.get(command_name, ""))(func)

    def _init_repacker(
        self,
        config: str,
        init_filelist_flag: bool = True,
        ignore_clean: bool = False,
        dlogger: DynamicLogger | None = None,
    ):
        self.repacker = Repacker(verbose=self.verbose, console=self.console, dlogger=dlogger)
        self.repacker.init_data(config_path=config, init_filelist_flag=init_filelist_flag, ignore_clean=ignore_clean)

    def _print(self, s: str | Panel):
        tui_print(self.console, s, verbose=self.verbose)

    def _log(self, s: str):
        tui_log(self.console, s, verbose=self.verbose)

    def _update_log(self, new_line: str):
        self._log_content.append(new_line)
        self.layout["logs"].update(Text("\n".join(self._log_content)))

    def cmd_list(
        self,
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
        self.verbose = verbose
        self._init_repacker(config, ignore_clean=True)
        self.repacker.print_list()

    # 采用 rich.progress 实现进度条效果
    # 引入 CPU 线程池，提高任务执行效率 20230429
    # 更改 CPU 线程池为 CPU 进程池 20230521
    # 弃用多进程/多线程，改用异步 20230525
    # 移除所有多进程/多线程/协程模块 20230528
    # 使用上下文管理器进行封装 20231228
    # 主进程完全重构 20240201
    # 使用 typer 重构交互功能 20250128
    def cmd_convert(
        self,
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
        log_lines: Annotated[
            int,
            typer.Option(
                "--log-lines", "-l", help="Number of log lines to display", rich_help_panel="Override Options"
            ),
        ] = 8,
    ):
        if quiet:
            logo = False
            progress = False
            taskbar = False
            verbose = False

        self.verbose = verbose

        self.pb = generate_progress_bar(console=self.console)
        self.win_tb: WinTaskbar | None = None

        self.layout = Layout()
        self.layout.split_column(
            Layout(name="logs", size=log_lines),
            Layout(name="status", size=1),
            Layout(name="progress", size=1),
        )

        self._log_content = deque(maxlen=log_lines)

        # 键盘Ctrl+C中断命令优化
        def keyboard_handler(signum, frame):
            try:
                # 重置进度条
                if self.pb is not None:
                    self.pb.stop()
                if self.win_tb is not None:
                    self.win_tb.reset_taskbar_progress()
                if self.live is not None:
                    self.live.stop()

                # 选择是否保留已转换文件和缓存文件夹
                self._log("[yellow]您手动中断了程序。")
                resp_out = Prompt.ask("请选择是否保留已转换文件", choices=["y", "n"], default="y")
                resp_cache = Prompt.ask("请选择是否保留缓存文件夹", choices=["y", "n"], default="n")
                # 除打包阶段使用的当前电子书文件外，其他文件均可清除
                # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
                if resp_out == "n":
                    os.chdir(self.repacker.input_dir)  # 防止进程占用输出文件夹 20230429
                    remove_if_exists(self.repacker.output_dir, recreate=True)
                if resp_cache != "y":
                    os.chdir(self.repacker.input_dir)  # 防止进程占用缓存文件夹 20230429
                    remove_if_exists(self.repacker.cache_dir)
            finally:
                exit(0)

        # 将主要执行过程封装，用于单线程或多线程时调用 20230429
        # 将执行过程提取到主函数外部 20230521
        def work(file_t: ComicFile):
            self.repacker.repack(file_t)

        def _convert() -> bool:
            filelist = self.repacker.filelist
            if not progress:
                for i, file_t in enumerate(filelist):
                    work(file_t)
            else:
                with ProgressController(
                    pb=self.pb,
                    tb=self.win_tb,
                    description="Kmoe",
                    total=len(filelist),
                ) as pctrl:
                    pctrl: ProgressController
                    for i, file_t in enumerate(filelist):
                        work(file_t)
                        pctrl.update(i)

            if self.repacker.faillist:
                self._print("[yellow]提示：以下文件转换失败！")
                indent: str = " " * 11
                for file_t in self.repacker.faillist:
                    self._print(f"{indent}{file_t.relative_path}")
                return True

            return False

        # 优化键盘中断命令
        import signal

        signal.signal(signal.SIGINT, keyboard_handler)
        signal.signal(signal.SIGTERM, keyboard_handler)

        # 欢迎界面
        if logo:
            self._print(welcome_panel)

        # 初始化转换器对象
        self._init_repacker(config, dlogger=self.dlogger)

        # 增加 docker build 风格状态显示 20250131
        self.dlogger.init_log_layout(self.layout["logs"])
        self.dlogger.update("")
        self.status = self.dlogger.status
        self.layout["status"].update(self.status)
        self.layout["progress"].update(self.pb)

        with Live(self.layout, auto_refresh=True) as self.live:
            self.status.update("[yellow]⏳ 开始初始化程序 ...")
            if taskbar:
                self.win_tb = create_wintaskbar_object()

            self.status.update("[yellow]⏳ 开始提取图片并打包文件...")

            pause = _convert()

            if not keep_cache:
                self.status.update("[yellow]⏳ 开始清理缓存文件...")
                self.repacker.clean_cache()

            self.dlogger.update_log("[green]✅ 所有转换任务完成！")

            if pause:
                self.status.update("[yellow]请按任意键继续...")
                self.console.input("")

    def cmd_clean(
        self,
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
        self.verbose = verbose

        with self.console.status("[yellow]⏳ 开始初始化程序 ...") as status:
            self._init_repacker(config, init_filelist_flag=False)

            if all:
                cache = True
                output = True

            if cache:
                status.update("[yellow]⏳ 开始清理缓存文件...")
                self.repacker.clean_cache()
                sleep(2)
                self._log("[green]✅ 已完成缓存文件清理。")

            if input:
                status.update("[yellow]⏳ 开始清理输入文件...")
                self.repacker.clean_input()
                sleep(2)
                self._log("[green]✅ 已完成输入文件清理。")

            if output:
                status.update("[yellow]⏳ 开始清理输出文件...")
                self.repacker.clean_output()
                sleep(2)
                self._log("[green]✅ 已完成输出文件清理。")

    def cmd_version(self):
        self._print(welcome_logo)
        self._print(
            f"𝒎​𝒐​𝒙​𝒎​𝒐​𝒆​ ​𝒓​𝒆​𝒑​𝒂​𝒄​𝒌​𝒆​𝒓 [bold cyan]v{self.app_version}[/], by [bold cyan]{self.author}[/], [bold cyan]{self.year}[/]",
        )


if __name__ == "__main__":
    app = Application()
    app.typer_app()
