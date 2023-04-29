# 主程序引用库
import moe_utils.file_system as mfst
import moe_utils.manga_repacker as mmrp
import moe_utils.taskbar_indicator as mtbi
import concurrent.futures
import os

# 程序显示引用库
from rich.prompt import Prompt
from rich.console import Console
import moe_utils.terminal_ui as mtui

##############################

# 键盘Ctrl+C中断命令优化
def keyboardHandler(signum, frame):
    try:
        # 重置进度条
        global repacker, taskbar, hWnd
        repacker.progress.stop()
        mtbi.resetTaskbarProgress(taskbar, hWnd)
        
        # 多线程状态下终止所有线程
        if repacker.multithread_on:
            try:
                global executor
                executor.shutdown(wait=False, cancel_futures=True)
            except:
                raise Exception('Thread not cancelled normally.')            
        
        # 选择是否保留已转换文件和缓存文件夹
        repacker.print(f'[yellow]您手动中断了程序。')
        resp_out = Prompt.ask("请选择是否保留已转换文件", choices=["y", "n"], default="y")
        resp_cache = Prompt.ask("请选择是否保留缓存文件夹", choices=["y", "n"], default="n")
        # 除打包阶段使用的当前电子书文件外，其他文件均可清除
        # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
        if resp_out == 'n':
            os.chdir(repacker.curr_path) # 防止进程占用输出文件夹 20230429
            mfst.removeIfExists(repacker.output_path)
        if resp_cache != 'y':
            os.chdir(repacker.curr_path) # 防止进程占用缓存文件夹 20230429
            mfst.removeIfExists(repacker.cachefolder)
    finally:
        exit(0)

# 主程序
if __name__ == '__main__':
    # 优化键盘中断命令
    import signal
    signal.signal(signal.SIGINT, keyboardHandler)
    signal.signal(signal.SIGTERM, keyboardHandler)
    
    # 采用 rich.traceback 作为默认异常打印
    from rich.traceback import install
    install(show_locals=True)
    
    # 初始化 Windows 任务栏对象
    taskbar, hWnd = mtbi.initWindowsTaskbar()
    
    # 欢迎界面
    Console().print(mtui.welcome_panel)
    
    # 初始化转换器对象
    repacker = mmrp.Repacker('./config.conf')    
    
    # 采用 rich.progress 实现进度条效果
    repacker.log(f'[yellow]开始提取图片并打包文件...')
    repacker.progress.start()
    total = len(repacker.curr_filelist)
    task = repacker.progress.add_task(description='Kox.moe', total=total)
    
    # 将主要执行过程封装，用于单线程或多线程时调用 20230429
    def work(elem):
        i, file_t = elem
        mtbi.setTaskbarProgress(taskbar, hWnd, i, total)
        repacker.repack(file_t)
        repacker.progress.update(task, advance=1)
    
    # 引入 CPU 线程池，提高任务执行效率 20230429
    if repacker.multithread_on:
        with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            _ = executor.map(work, enumerate(repacker.curr_filelist))
    else:
        for elem in enumerate(repacker.curr_filelist):
            work(elem)
            
    repacker.progress.stop()
    mtbi.resetTaskbarProgress(taskbar, hWnd)

    repacker.log(f'[yellow]开始清理缓存文件...')
    os.chdir(repacker.output_path) # 防止进程占用缓存文件夹 20230429
    mfst.removeIfExists(repacker.cachefolder)
    
    repacker.log(f'[green]所有转换任务完成！')
