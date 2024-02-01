# 主程序引用库
import os
from pathlib import Path
from contextlib import AbstractContextManager
from types import TracebackType
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter

# 程序显示引用库
from rich.prompt import Prompt

# 程序异常打印库
from rich.traceback import install

from rich.progress import Progress, TaskID

from moe_utils.file_system import remove_if_exists
from moe_utils.manga_repacker import IRepacker, Repacker
from moe_utils.progress_bar import generate_progress_bar
from moe_utils.taskbar_indicator import WinTaskbar, create_wintaskbar_object
from moe_utils.terminal_ui import welcome_logo, welcome_panel

install(show_locals=True)

##############################


# 使用上下文管理器进行封装 20231228
class ProgressController(AbstractContextManager):
    pb: Progress
    tb: WinTaskbar | None = None
    tb_imported: bool = False
    description: str
    total: int
    task: TaskID

    def __init__(
        self, pb: Progress, tb: WinTaskbar | None, description: str, total: int
    ):
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

    def __exit__(
        self,
        __exc_type: type[BaseException] | None,
        __exc_value: BaseException | None,
        __traceback: TracebackType | None,
    ) -> bool | None:
        self.pb.stop()
        if self.tb_imported:
            self.tb.reset_taskbar_progress()
        return super().__exit__(__exc_type, __exc_value, __traceback)

    def update(self, i: int):
        self.pb.update(self.task, advance=1)
        if self.tb_imported:
            self.tb.set_taskbar_progress(i, self.total)


# 主进程完全重构 20240201
class Application(IRepacker):
    pb: Progress
    win_tb: WinTaskbar | None = None
    repacker: Repacker
    parser: ArgumentParser
    args: Namespace

    def __init__(self, verbose: bool = True):
        self.pb = generate_progress_bar()
        self._init_parser()
        self.args = self.parser.parse_args()

        if self.args.quiet:
            self.args.no_logo = True
            self.args.no_progress = True
            self.args.no_taskbar = True
            self.args.no_verbose = True

        if self.args.list or self.args.no_verbose:
            verbose = False

        super().__init__(verbose=verbose, console=self.pb.console)

    def _init_parser(self):
        # 命令行参数列表 20231230
        self.parser = ArgumentParser(
            description=welcome_logo, formatter_class=RawTextHelpFormatter
        )
        self.parser.add_argument(
            "-i", "--input-dir", type=str, default=None, help="Input Directory Path"
        )
        self.parser.add_argument(
            "-o", "--output-dir", type=str, default=None, help="Output Directory Path"
        )
        self.parser.add_argument(
            "-cc", "--cache-dir", type=str, default=None, help="Cache Directory Path"
        )
        self.parser.add_argument(
            "-cl",
            "--clean-all",
            action="store_true",
            help="Clean Output and Cache files",
        )
        self.parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="Only list documents without conversion",
        )
        self.parser.add_argument(
            "-nt",
            "--no-taskbar",
            action="store_true",
            help="Disable Taskbar Progress Display",
        )
        self.parser.add_argument(
            "-nl", "--no-logo", action="store_true", help="Disable Logo"
        )
        self.parser.add_argument(
            "-np", "--no-progress", action="store_true", help="Disable Progress Bar"
        )
        self.parser.add_argument(
            "-nv", "--no-verbose", action="store_true", help="Disable Verbose Output"
        )
        self.parser.add_argument(
            "-q", "--quiet", action="store_true", help="Quiet Mode"
        )

    def _clean_cache(self):
        self.log("[yellow]开始清理缓存文件...")
        remove_if_exists(self.repacker.cache_dir)

    def _clean_output(self):
        self.log("[yellow]开始清理输出文件...")
        remove_if_exists(self.repacker.output_dir)
        os.mkdir(self.repacker.output_dir)

    def _convert(self):
        # 采用 rich.progress 实现进度条效果
        # 引入 CPU 线程池，提高任务执行效率 20230429
        # 更改 CPU 线程池为 CPU 进程池 20230521
        # 弃用多进程/多线程，改用异步 20230525
        # 移除所有多进程/多线程/协程模块 20230528
        # 使用上下文管理器进行封装 20231228
        if self.args.no_progress:
            for i, file_t in enumerate(self.repacker.filelist):
                self.work(file_t)
        else:
            with ProgressController(
                pb=self.pb,
                tb=self.win_tb,
                description="Kox.moe",
                total=len(self.repacker.filelist),
            ) as pctrl:
                pctrl: ProgressController
                for i, file_t in enumerate(self.repacker.filelist):
                    self.work(file_t)
                    pctrl.update(i)

    # 键盘Ctrl+C中断命令优化
    def keyboard_handler(self, signum, frame):
        try:
            # 重置进度条
            self.pb.stop()
            if self.win_tb is not None:
                self.win_tb.reset_taskbar_progress()

            # 选择是否保留已转换文件和缓存文件夹
            self.console.print("[yellow]您手动中断了程序。")
            resp_out = Prompt.ask(
                "请选择是否保留已转换文件", choices=["y", "n"], default="y"
            )
            resp_cache = Prompt.ask(
                "请选择是否保留缓存文件夹", choices=["y", "n"], default="n"
            )
            # 除打包阶段使用的当前电子书文件外，其他文件均可清除
            # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
            if resp_out == "n":
                os.chdir(self.repacker.input_dir)  # 防止进程占用输出文件夹 20230429
                remove_if_exists(self.repacker.output_dir)
            if resp_cache != "y":
                os.chdir(self.repacker.input_dir)  # 防止进程占用缓存文件夹 20230429
                remove_if_exists(self.repacker.cache_dir)
        finally:
            exit(0)

    # 将主要执行过程封装，用于单线程或多线程时调用 20230429
    # 将执行过程提取到主函数外部 20230521
    def work(self, file_t: Path):
        self.repacker.repack(file_t)

    # 主程序
    def main(self):
        # 优化键盘中断命令
        import signal

        signal.signal(signal.SIGINT, self.keyboard_handler)
        signal.signal(signal.SIGTERM, self.keyboard_handler)

        # 欢迎界面
        if not self.args.no_logo:
            self.console.print(welcome_panel)

        # 初始化转换器对象
        self.repacker = Repacker(verbose=self.verbose, console=self.console)
        self.repacker.init_data(config_path="./config.toml", args=self.args)

        # 若存在参数 cl，则运行清理命令并退出 20231230
        if self.args.clean_all:
            self._clean_cache()
            self._clean_output()
            return

        # 若存在参数 ls，则不进行转换，仅打印目录列表
        if self.args.list:
            self.repacker.print_list()
            return

        # 若存在参数 nt，则不加载任务栏进度条
        self.win_tb = None
        if not self.args.no_taskbar:
            self.win_tb = create_wintaskbar_object()

        self.log("[yellow]开始提取图片并打包文件...")

        self._convert()

        self._clean_cache()

        self.log("[green]所有转换任务完成！")


if __name__ == "__main__":
    app = Application()
    app.main()
