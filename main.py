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

import moe_utils.file_system as mfst
import moe_utils.manga_repacker as mmrp
import moe_utils.progress_bar as mpbr
import moe_utils.taskbar_indicator as mtbi
import moe_utils.terminal_ui as mtui

install(show_locals=True)

##############################

# 全局初始化 Repacker 对象 20230521
pb = mpbr.generateProgressBar()
console = pb.console
repacker = mmrp.Repacker(console=console)

# 全局初始化 Windows 任务栏对象 20230521
win_tb: mtbi.WinTaskbar | None = None


# 使用上下文管理器进行封装 20231228
class ProgressController(AbstractContextManager):
    pb: Progress
    tb: mtbi.WinTaskbar | None = None
    tb_imported: bool = False
    description: str
    total: int
    task: TaskID

    def __init__(
        self, pb: Progress, tb: mtbi.WinTaskbar | None, description: str, total: int
    ):
        super().__init__()
        self.pb = pb
        self.tb = tb
        self.tb_imported = isinstance(tb, mtbi.WinTaskbar)
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


# 键盘Ctrl+C中断命令优化
def keyboard_handler(signum, frame):
    try:
        # 重置进度条
        global repacker, console, win_tb, pb
        pb.stop()
        if win_tb is not None:
            win_tb.reset_taskbar_progress()

        # 选择是否保留已转换文件和缓存文件夹
        console.print("[yellow]您手动中断了程序。")
        resp_out = Prompt.ask(
            "请选择是否保留已转换文件", choices=["y", "n"], default="y"
        )
        resp_cache = Prompt.ask(
            "请选择是否保留缓存文件夹", choices=["y", "n"], default="n"
        )
        # 除打包阶段使用的当前电子书文件外，其他文件均可清除
        # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
        if resp_out == "n":
            os.chdir(repacker.input_dir)  # 防止进程占用输出文件夹 20230429
            mfst.remove_if_exists(repacker.output_dir)
        if resp_cache != "y":
            os.chdir(repacker.input_dir)  # 防止进程占用缓存文件夹 20230429
            mfst.remove_if_exists(repacker.cache_dir)
    finally:
        exit(0)


# 将主要执行过程封装，用于单线程或多线程时调用 20230429
# 将执行过程提取到主函数外部 20230521
def work(file_t: Path):
    repacker.repack(file_t)


# 主程序
def main():
    # 优化键盘中断命令
    import signal

    signal.signal(signal.SIGINT, keyboard_handler)
    signal.signal(signal.SIGTERM, keyboard_handler)

    # 命令行参数列表 20231230
    parser = ArgumentParser(
        description=mtui.welcome_logo, formatter_class=RawTextHelpFormatter
    )
    parser.add_argument(
        "-if", "--input-dir", type=str, default=None, help="Input Directory Path"
    )
    parser.add_argument(
        "-of", "--output-dir", type=str, default=None, help="Output Directory Path"
    )
    parser.add_argument(
        "-cc", "--cache-dir", type=str, default=None, help="Cache Directory Path"
    )
    parser.add_argument(
        "-cl", "--clean-all", action="store_true", help="Clean Output and Cache files"
    )
    parser.add_argument(
        "-nt",
        "--no-taskbar",
        action="store_true",
        help="Disable Taskbar Progress Display",
    )
    parser.add_argument("-nl", "--no-logo", action="store_true", help="Disable Logo")
    args: Namespace = parser.parse_args()

    # 欢迎界面
    if not args.no_logo:
        console.print(mtui.welcome_panel)

    # 初始化转换器对象
    repacker.init_data(config_path="./config.toml", args=args)

    # 若存在参数 cl，则运行清理命令并退出 20231230
    if args.clean_all:
        mtui.log(console, "[yellow]开始清理输出文件...")
        mfst.remove_if_exists(repacker.output_dir)
        os.mkdir(repacker.output_dir)
        mtui.log(console, "[yellow]开始清理缓存文件...")
        mfst.remove_if_exists(repacker.cache_dir)
        return

    # 若存在参数 nt，则不加载任务栏进度条
    win_tb = None
    if not args.no_taskbar:
        win_tb = mtbi.create_wintaskbar_object()

    # 采用 rich.progress 实现进度条效果
    mtui.log(console, "[yellow]开始提取图片并打包文件...")

    # 引入 CPU 线程池，提高任务执行效率 20230429
    # 更改 CPU 线程池为 CPU 进程池 20230521
    # 弃用多进程/多线程，改用异步 20230525
    # 移除所有多进程/多线程/协程模块 20230528
    # 使用上下文管理器进行封装 20231228
    with ProgressController(
        pb=pb, tb=win_tb, description="Kox.moe", total=len(repacker.filelist)
    ) as pctrl:
        pctrl: ProgressController
        for i, file_t in enumerate(repacker.filelist):
            work(file_t)
            pctrl.update(i)

    mtui.log(console, "[yellow]开始清理缓存文件...")
    os.chdir(repacker.output_dir)  # 防止进程占用缓存文件夹 20230429
    mfst.remove_if_exists(repacker.cache_dir)

    mtui.log(console, "[green]所有转换任务完成！")


if __name__ == "__main__":
    main()
