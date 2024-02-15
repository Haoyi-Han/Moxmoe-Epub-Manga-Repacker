import importlib
import time
import platform
from functools import wraps


def is_NT() -> bool:
    return platform.system().lower().startswith("win")


def on_windows(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if is_NT():
            return func(*args, **kwargs)

    return wrapper


def global_imports(modulename: str, alias: str | None = None):
    globals()[alias if alias else modulename] = importlib.import_module(modulename)


@on_windows
def importTaskbarAPI():
    global_imports("comtypes.client", "cc")
    global_imports("win32api")
    global_imports("win32gui")


class WinTaskbar:
    def __init__(self):
        self.taskbar, self.hWnd = self.initWindowsTaskbar()

    @on_windows
    def initWindowsTaskbar(self):
        # importTaskbarAPI() # 经试验本函数工作正常，但由于导入行为在运行期，因此各 IDE 均会认为存在未导入的包
        import comtypes.client as cc
        import win32api
        import win32gui

        taskbar, hWnd = None, None
        cc.GetModule("./tl.tlb")
        import comtypes.gen.TaskbarLib as tbl

        taskbar = cc.CreateObject(
            "{56FDF344-FD6D-11d0-958A-006097C9A090}", interface=tbl.ITaskbarList3
        )
        taskbar.HrInit()

        # find hWnd of the console
        title = win32api.GetConsoleTitle()
        tag = title  # + '___' # 此处不知为何更改后找不到句柄
        win32api.SetConsoleTitle(tag)
        time.sleep(0.05)
        hWnd = win32gui.FindWindow(None, tag)
        win32api.SetConsoleTitle(title)
        return taskbar, hWnd

    @on_windows
    def set_taskbar_progress(self, i, total):
        self.taskbar.SetProgressValue(self.hWnd, i, total)
        self.taskbar.SetProgressState(self.hWnd, 0x2)

    @on_windows
    def reset_taskbar_progress(self):
        self.taskbar.SetProgressState(self.hWnd, 0x0)


def create_wintaskbar_object() -> WinTaskbar | None:
    try:
        if is_NT():
            return WinTaskbar()
        else:
            return None
    except ImportError:
        return None
    except FileNotFoundError:
        return None
    except OSError:
        return None
