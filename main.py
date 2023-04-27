# 主程序引用库
import moe_utils.file_system as mfst
import moe_utils.manga_repacker as mmrp
import moe_utils.utils as mutl
import moe_utils.taskbar_indicator as mtbi

# 程序配置引用库
import signal
import configparser as cp

# 程序显示引用库
from rich.box import DOUBLE
from rich.panel import Panel

# 程序调试引用库
from rich.traceback import install

##############################

# 键盘Ctrl+C中断命令优化
def keyboardHandler(signum, frame):
    try:
        # 重置进度条
        global repacker, taskbar, hWnd
        repacker.progress.stop()
        mtbi.resetTaskbarProgress(taskbar, hWnd)
        
        # 选择是否保留已转换文件和缓存文件夹
        global output_path, cachefolder
        print(f'\033[93m您手动中断了程序。\033[0m')
        resp_out = input('请选择是否保留已转换文件(Y/N，默认选Y)：')
        resp_cache = input('请选择是否保留缓存文件夹(Y/N，默认选N)：')
        # 除打包阶段使用的当前电子书文件外，其他文件均可清除
        # 之后会考虑将打包阶段作为独立进程，并在中断退出时结束
        if resp_out == 'N' or resp_out == 'n':
            mfst.removeIfExists(output_path)
        if resp_cache != 'Y' or resp_cache != 'y':
            mfst.removeIfExists(cachefolder)
    finally:
        exit(0)

# 主程序
if __name__ == '__main__':
    # 优化键盘中断命令
    signal.signal(signal.SIGINT, keyboardHandler)
    signal.signal(signal.SIGTERM, keyboardHandler)
    
    # 采用 rich.traceback 作为默认异常打印
    install(show_locals=True)
    
    # 初始化 Windows 任务栏对象
    taskbar, hWnd = mtbi.initWindowsTaskbar()
    
    # 欢迎界面
    repacker = mmrp.Repacker()
    welcome_panel = Panel.fit(
                  " [bold cyan]支持 [green]Vol.moe[/] & [green]Mox.moe[/] & [green]Kox.moe[/] 下载的漫画文件转换。[/] ", 
                  box=DOUBLE,
                  title=" [bold green]Mox.moe EPUB Manga Repacker[/] ",
                  border_style="cyan",
                  padding=(1, 4)
                 )
    repacker.progress.console.print(welcome_panel)
    
    repacker.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] [yellow]开始初始化程序...')
    config = cp.ConfigParser()
    config.read('./config.conf')
    curr_path, output_path, curr_filelist = repacker.initPathObj(
        use_curr_as_input_dir=config.getboolean('DEFAULT', 'UseCurrentDirAsInput'),
        input_dir=config['DEFAULT']['InputDir'],
        create_output_folder_under_input_dir=config.getboolean('DEFAULT', 'CreateOutputDirUnderInputDir'),
        output_dir=config['DEFAULT']['OutputDir'],
        output_folder=config['DEFAULT']['OutputFolder'],
        exclude=config['DEFAULT']['Exclude'].split('||')
        )
    cachefolder = curr_path / 'cache'
    
    repacker.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] [yellow]开始提取图片并打包文件...')
    # 进度条效果
    # 用 rich.progress 代替 alive_progress，代码更简，外观更美观
    repacker.progress.start()
    total = len(curr_filelist)
    task = repacker.progress.add_task(description='Kox.moe', total=total)
    for i, file_t in enumerate(curr_filelist):
        mtbi.setTaskbarProgress(taskbar, hWnd, i, total)
        comic_name: str = file_t.parents[0].name
        comic_src = repacker.loadZipImg(file_t, cachefolder=cachefolder)
        if comic_name == curr_path.stem:
            repacker.packFolder(comic_src, output_path)
        else:
            repacker.packFolder(comic_src, output_path / comic_name)
        mfst.removeIfExists(cachefolder / comic_name)
        repacker.progress.update(task, advance=1)
    repacker.progress.stop()
    mtbi.resetTaskbarProgress(taskbar, hWnd)

    repacker.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] [yellow]开始清理缓存文件...')
    mfst.removeIfExists(cachefolder)
    
    repacker.progress.console.print(f'[blue][{mutl.currTimeFormat()}][/] [green]所有转换任务完成！')
