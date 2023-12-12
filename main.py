# 主程序引用库
import os
import pathlib

# 程序显示引用库
from rich.prompt import Prompt
# 程序异常打印库
from rich.traceback import install

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
win_tb = mtbi.WinTaskbar()


# 键盘Ctrl+C中断命令优化
def keyboard_handler(signum, frame):
    try:
        # 重置进度条
        global repacker, console, win_tb, pb
        pb.stop()
        win_tb.reset_taskbar_progress()

        # 选择是否保留已转换文件和缓存文件夹
        console.print('[yellow]您手动中断了程序。')
        resp_out = Prompt.ask("请选择是否保留已转换文件", choices=["y", "n"], default="y")
        resp_cache = Prompt.ask("请选择是否保留缓存文件夹", choices=["y", "n"], default="n")
        # 除打包阶段使用的当前电子书文件外，其他文件均可清除
        # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
        if resp_out == 'n':
            os.chdir(repacker.input_dir)  # 防止进程占用输出文件夹 20230429
            mfst.remove_if_exists(repacker.output_dir)
        if resp_cache != 'y':
            os.chdir(repacker.input_dir)  # 防止进程占用缓存文件夹 20230429
            mfst.remove_if_exists(repacker.cache_dir)
    finally:
        exit(0)


# 将主要执行过程封装，用于单线程或多线程时调用 20230429
# 将执行过程提取到主函数外部 20230521
def work(file_t):
    repacker.repack(pathlib.Path(file_t))


# 主程序
def main():
    # 优化键盘中断命令
    import signal
    signal.signal(signal.SIGINT, keyboard_handler)
    signal.signal(signal.SIGTERM, keyboard_handler)

    # 欢迎界面
    console.print(mtui.welcome_panel)

    # 初始化转换器对象
    repacker.init_from_config('./config.toml')

    # 采用 rich.progress 实现进度条效果
    mtui.log(console, '[yellow]开始提取图片并打包文件...')
    pb.start()
    total = len(repacker.filelist)
    task = pb.add_task(description='Kox.moe', total=total)

    # 引入 CPU 线程池，提高任务执行效率 20230429
    # 更改 CPU 线程池为 CPU 进程池 20230521
    # 弃用多进程/多线程，改用异步 20230525
    # 移除所有多进程/多线程/协程模块 20230528
    for i, file_t in enumerate(repacker.filelist):
        work(file_t)
        win_tb.set_taskbar_progress(i, total)
        pb.update(task, advance=1)

    pb.stop()
    win_tb.reset_taskbar_progress()

    mtui.log(console, '[yellow]开始清理缓存文件...')
    os.chdir(repacker.output_dir)  # 防止进程占用缓存文件夹 20230429
    mfst.remove_if_exists(repacker.cache_dir)

    mtui.log(console, '[green]所有转换任务完成！')


if __name__ == '__main__':
    main()
