import importlib
import platform
import time

def on_windows(func):
    def wrapper(*args, **kwargs):
        if platform.system() == 'Windows':
            return func(*args, **kwargs)
    return wrapper
            
def global_imports(modulename: str, alias: str=None):
    globals()[alias if alias else modulename] = importlib.import_module(modulename)

@on_windows            
def importTaskbarAPI():
    global_imports("comtypes.client", "cc")
    global_imports("win32api")
    global_imports("win32gui")

@on_windows
def initWindowsTaskbar():
    #importTaskbarAPI()
    import comtypes.client as cc
    import win32api, win32gui
    taskbar, hWnd = None, None
    cc.GetModule('./tl.tlb')
    import comtypes.gen.TaskbarLib as tbl
    taskbar = cc.CreateObject('{56FDF344-FD6D-11d0-958A-006097C9A090}', interface=tbl.ITaskbarList3)
    taskbar.HrInit()

    # find hWnd of the console
    title = win32api.GetConsoleTitle()
    tag = title# + '___' # 此处不知为何更改后找不到句柄
    win32api.SetConsoleTitle(tag)
    time.sleep(0.05)
    hWnd = win32gui.FindWindow(None, tag)
    win32api.SetConsoleTitle(title)
    assert hWnd
    return taskbar, hWnd

@on_windows
def setTaskbarProgress(taskbar, hWnd, i, total):
    taskbar.SetProgressValue(hWnd, i, total)
    taskbar.SetProgressState(hWnd, 0x2)
    
@on_windows
def resetTaskbarProgress(taskbar, hWnd):
    taskbar.SetProgressState(hWnd, 0x0)

