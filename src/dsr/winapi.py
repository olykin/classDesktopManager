# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""Windows 原生 API 封装（纯 ctypes，无第三方依赖）。

包含：DPI 感知、已知文件夹路径、驱动器类型、开机自启动注册表、
单实例互斥体、工作区尺寸等。
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)

# ------------------------------------------------------------------ 常量
GWL_EXSTYLE = -20
GWL_STYLE = -16
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
SW_SHOWNORMAL = 1
SW_RESTORE = 9
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
WM_DESTROY = 0x0002
WM_CLOSE = 0x0010
WM_TIMER = 0x0113
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_NULL = 0x0000
WM_APP = 0x8000
WM_TRAYICON = WM_APP + 1
DIALOG_APP = WM_APP + 100
NIM_ADD = 0
NIM_MODIFY = 1
NIM_DELETE = 2
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
NIF_INFO = 0x10
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512
IDC_ARROW = 32512
MF_STRING = 0x00000000
MF_SEPARATOR = 0x00000800
MF_GRAYED = 0x00000001
MF_DISABLED = 0x00000002
MF_CHECKED = 0x00000008
TPM_LEFTALIGN = 0x0000
TPM_CENTERALIGN = 0x0004
TPM_RIGHTALIGN = 0x0008
TPM_BOTTOMALIGN = 0x0020
TPM_TOPALIGN = 0x0000
TPM_VCENTERALIGN = 0x0010
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080
TPM_RIGHTBUTTON = 0x0002
SPI_GETWORKAREA = 0x0030
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
COLOR_WINDOW = 5
DT_CENTER = 0x00000001
DT_VCENTER = 0x00000004
DT_SINGLELINE = 0x00000020
DT_NOPREFIX = 0x00000800

# 窗口消息
WM_PAINT = 0x000F
WM_ERASEBKGND = 0x0014
WM_SETCURSOR = 0x0020
WM_NCHITTEST = 0x0084
WM_MOUSELEAVE = 0x02A3
WM_CAPTURECHANGED = 0x0215
WM_ACTIVATE = 0x0006
WM_DPICHANGED = 0x02E0
WM_COMMAND = 0x0111
WM_KEYDOWN = 0x0100
WM_ENDSESSION = 0x0016
WM_QUERYENDSESSION = 0x0011

# 命中测试
HTTRANSPARENT = -1
HTCLIENT = 1
HTCAPTION = 2

# 系统光标
IDC_HAND = 32649
IDC_ARROW_ = 32512

# 系统指标
SM_CXICON = 11
SM_CYICON = 12
SM_CXSMICON = 49
SM_CYSMICON = 50

TME_LEAVE = 0x00000002
DIB_RGB_COLORS = 0

# 菜单命令
IDM_SHOW = 1001
IDM_SETTINGS = 1002
IDM_PAUSE = 1003
IDM_OPEN_DESKTOP = 1004
IDM_CHECK = 1005
IDM_EXIT = 1006


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


# {B4BFCC3A-DB2C-424C-B029-7FE99A87C641}  FOLDERID_Desktop
FOLDERID_Desktop = GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                        (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9,
                                             0x9A, 0x87, 0xC6, 0x41))

# {374DE290-123F-4565-9164-39C4925E467B}  FOLDERID_Downloads
FOLDERID_Downloads = GUID(0x374DE290, 0x123F, 0x4565,
                          (ctypes.c_ubyte * 8)(0x91, 0x64, 0x39, 0xC4,
                                               0x92, 0x5E, 0x46, 0x7B))


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte),
                ("AlphaFormat", ctypes.c_ubyte)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT,
                             ctypes.c_ulonglong, ctypes.c_longlong)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD)]


MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0


class TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD),
                ("hwndTrack", wintypes.HWND),
                ("dwHoverTime", wintypes.DWORD)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", ctypes.c_ulonglong),
                ("lParam", ctypes.c_longlong),
                ("time", wintypes.DWORD),
                ("pt", POINT)]


PM_NOREMOVE = 0x0000

# ------------------------------------------------------------ 函数原型绑定
def _bind(func, argtypes, restype):
    func.argtypes = argtypes
    func.restype = restype
    return func


_SetProcessDpiAwarenessContext = getattr(user32, "SetProcessDpiAwarenessContext", None)
if _SetProcessDpiAwarenessContext is not None:
    _bind(_SetProcessDpiAwarenessContext, [ctypes.c_void_p], wintypes.BOOL)
_SetProcessDPIAware = getattr(user32, "SetProcessDPIAware", None)
if _SetProcessDPIAware is not None:
    _bind(_SetProcessDPIAware, [], wintypes.BOOL)

_bind(user32.GetDC, [wintypes.HWND], wintypes.HDC)
_bind(user32.ReleaseDC, [wintypes.HWND, wintypes.HDC], ctypes.c_int)
_bind(gdi32.GetDeviceCaps, [wintypes.HDC, ctypes.c_int], ctypes.c_int)
_bind(user32.GetSystemMetrics, [ctypes.c_int], ctypes.c_int)
_bind(user32.SystemParametersInfoW,
      [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT], wintypes.BOOL)
_bind(user32.SetWindowPos,
      [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
       ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL)
_bind(user32.GetCursorPos, [ctypes.POINTER(POINT)], wintypes.BOOL)
try:
    _bind(user32.MonitorFromPoint, [POINT, wintypes.DWORD], ctypes.c_void_p)
    _bind(user32.GetMonitorInfoW, [ctypes.c_void_p, ctypes.POINTER(MONITORINFO)],
          wintypes.BOOL)
except Exception:                                   # pragma: no cover
    pass
shcore = None
try:
    shcore = ctypes.WinDLL("shcore")
    _bind(shcore.GetDpiForMonitor,
          [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
           ctypes.POINTER(ctypes.c_uint)], ctypes.c_long)
except Exception:                                   # pragma: no cover
    shcore = None
_GetDpiForWindow = getattr(user32, "GetDpiForWindow", None)
if _GetDpiForWindow is not None:
    _bind(_GetDpiForWindow, [wintypes.HWND], ctypes.c_uint)
_bind(user32.DestroyWindow, [wintypes.HWND], wintypes.BOOL)
_bind(user32.DefWindowProcW, [wintypes.HWND, wintypes.UINT,
                              ctypes.c_ulonglong, ctypes.c_longlong], ctypes.c_longlong)
_bind(user32.GetMessageW, [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                           wintypes.UINT], ctypes.c_int)
_bind(user32.TranslateMessage, [ctypes.c_void_p], wintypes.BOOL)
_bind(user32.DispatchMessageW, [ctypes.c_void_p], ctypes.c_longlong)
_bind(user32.PostQuitMessage, [ctypes.c_int], None)
_bind(user32.PostMessageW, [wintypes.HWND, wintypes.UINT,
                            ctypes.c_ulonglong, ctypes.c_longlong], wintypes.BOOL)
_bind(user32.PostThreadMessageW, [wintypes.DWORD, wintypes.UINT,
                                  ctypes.c_ulonglong, ctypes.c_longlong], wintypes.BOOL)
_bind(user32.SetTimer, [wintypes.HWND, ctypes.c_size_t, wintypes.UINT,
                        ctypes.c_void_p], ctypes.c_size_t)
_bind(user32.KillTimer, [wintypes.HWND, ctypes.c_size_t], wintypes.BOOL)
_bind(user32.GetWindowLongPtrW, [wintypes.HWND, ctypes.c_int], ctypes.c_longlong)
_bind(user32.SetWindowLongPtrW, [wintypes.HWND, ctypes.c_int,
                                 ctypes.c_longlong], ctypes.c_longlong)
_bind(user32.SetForegroundWindow, [wintypes.HWND], wintypes.BOOL)
_bind(user32.FindWindowW, [wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND)
_bind(user32.IsWindow, [wintypes.HWND], wintypes.BOOL)
_bind(user32.ShowWindow, [wintypes.HWND, ctypes.c_int], wintypes.BOOL)
_bind(user32.LoadImageW, [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                          ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.HANDLE)
_bind(user32.LoadIconW, [wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HICON)
_bind(user32.CreatePopupMenu, [], wintypes.HMENU)
_bind(user32.AppendMenuW, [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t,
                           wintypes.LPCWSTR], wintypes.BOOL)
_bind(user32.TrackPopupMenu, [wintypes.HMENU, wintypes.UINT, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, wintypes.HWND,
                              ctypes.c_void_p], wintypes.UINT)
_bind(user32.DestroyMenu, [wintypes.HMENU], wintypes.BOOL)
_bind(user32.GetClientRect, [wintypes.HWND, ctypes.POINTER(RECT)], wintypes.BOOL)
_bind(user32.SetCursor, [wintypes.HANDLE], wintypes.HANDLE)
_bind(user32.RegisterWindowMessageW, [wintypes.LPCWSTR], wintypes.UINT)
_bind(user32.GetDpiForWindow, [wintypes.HWND], wintypes.UINT)
_bind(user32.RegisterClassExW, [ctypes.POINTER(WNDCLASSEXW)], wintypes.ATOM)
_bind(user32.UnregisterClassW, [wintypes.LPCWSTR, wintypes.HINSTANCE], wintypes.BOOL)
_bind(user32.CreateWindowExW,
      [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p],
      wintypes.HWND)
_bind(user32.GetWindowRect, [wintypes.HWND, ctypes.POINTER(RECT)], wintypes.BOOL)
_bind(user32.UpdateLayeredWindow,
      [wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
       wintypes.HDC, ctypes.POINTER(POINT), wintypes.DWORD,
       ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD], wintypes.BOOL)
_bind(user32.GetSystemMetrics, [ctypes.c_int], ctypes.c_int)
_bind(gdi32.CreateCompatibleDC, [wintypes.HDC], wintypes.HDC)
_bind(gdi32.DeleteDC, [wintypes.HDC], wintypes.BOOL)
_bind(gdi32.DeleteObject, [wintypes.HGDIOBJ], wintypes.BOOL)
_bind(shell32.Shell_NotifyIconW, [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)],
      wintypes.BOOL)
_bind(shell32.SHGetKnownFolderPath,
      [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
       ctypes.POINTER(ctypes.c_wchar_p)], ctypes.c_long)
_bind(kernel32.GetModuleHandleW, [wintypes.LPCWSTR], wintypes.HMODULE)
_bind(kernel32.CreateMutexW, [ctypes.c_void_p, wintypes.BOOL,
                              wintypes.LPCWSTR], wintypes.HANDLE)
_bind(kernel32.GetLastError, [], wintypes.DWORD)
_bind(kernel32.CloseHandle, [wintypes.HANDLE], wintypes.BOOL)
_bind(kernel32.GetDriveTypeW, [wintypes.LPCWSTR], wintypes.UINT)
_bind(kernel32.GetLogicalDriveStringsW, [wintypes.DWORD, wintypes.LPWSTR],
      wintypes.DWORD)
_bind(kernel32.GetCurrentThreadId, [], wintypes.DWORD)
_bind(ole32.CoTaskMemFree, [ctypes.c_void_p], None)
_bind(advapi32.RegCreateKeyExW,
      [wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPWSTR,
       wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
       ctypes.POINTER(wintypes.HKEY), ctypes.POINTER(wintypes.DWORD)], ctypes.c_long)
_bind(advapi32.RegSetValueExW,
      [wintypes.HKEY, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
       ctypes.c_void_p, wintypes.DWORD], ctypes.c_long)
_bind(advapi32.RegQueryValueExW,
      [wintypes.HKEY, wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p,
       ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)], ctypes.c_long)
_bind(advapi32.RegDeleteValueW, [wintypes.HKEY, wintypes.LPCWSTR], ctypes.c_long)
_bind(advapi32.RegCloseKey, [wintypes.HKEY], ctypes.c_long)

# ---- 分层窗口气泡 / 托盘所需
_bind(user32.LoadCursorW, [wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HANDLE)
_bind(user32.SetCapture, [wintypes.HWND], wintypes.HWND)
_bind(user32.ReleaseCapture, [], wintypes.BOOL)
_bind(user32.TrackMouseEvent, [ctypes.POINTER(TRACKMOUSEEVENT)], wintypes.BOOL)
_bind(user32.GetWindowLongPtrW, [wintypes.HWND, ctypes.c_int], ctypes.c_longlong)
_bind(gdi32.CreateDIBSection,
      [wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
       ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD],
      wintypes.HBITMAP)
_bind(gdi32.SelectObject, [wintypes.HDC, wintypes.HGDIOBJ], wintypes.HGDIOBJ)
_bind(ole32.CoInitializeEx, [ctypes.c_void_p, wintypes.DWORD], ctypes.c_long)
_bind(ole32.CoUninitialize, [], None)
_bind(user32.PeekMessageW,
      [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
       wintypes.UINT], wintypes.BOOL)
_bind(user32.GetMessageW, [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT,
                           wintypes.UINT], ctypes.c_int)
_bind(user32.TranslateMessage, [ctypes.POINTER(MSG)], wintypes.BOOL)
_bind(user32.DispatchMessageW, [ctypes.POINTER(MSG)], ctypes.c_longlong)

HKEY_CURRENT_USER = wintypes.HKEY(0x80000001)
KEY_QUERY_VALUE = 0x0001
KEY_SET_VALUE = 0x0002
REG_SZ = 1
ERROR_ALREADY_EXISTS = 183
ERROR_FILE_NOT_FOUND = 2

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

_CACHED_DPI_SCALE = None


# ---------------------------------------------------------------- 公共 API
def set_dpi_awareness():
    """按显示器 DPI 感知，保证高分屏下界面与气泡清晰。"""
    try:
        if _SetProcessDpiAwarenessContext is not None:
            # -4 = DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
            if _SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
                return
    except Exception:
        pass
    try:
        if _SetProcessDPIAware is not None:
            _SetProcessDPIAware()
    except Exception:
        pass


def dpi_awareness_name():
    """当前进程的 DPI 感知级别（排错用）。"""
    fn = getattr(user32, "GetAwarenessFromDpiAwarenessContext", None)
    get_ctx = getattr(user32, "GetThreadDpiAwarenessContext", None)
    try:
        if fn is not None and get_ctx is not None:
            ctx = get_ctx()
            v = fn(ctx)
            return {0: "unaware", 1: "system", 2: "per-monitor",
                    3: "per-monitor-v2", 4: "unaware-gdi"}.get(int(v), str(v))
    except Exception:
        pass
    return "unknown"


def dpi_debug():
    """一行 DPI 诊断信息（排错用，会真实查询，不读缓存之外的值）。"""
    try:
        tid = kernel32.GetCurrentThreadId()
    except Exception:
        tid = -1
    try:
        scale = dpi_scale()
        pt = dpi_scale_for_point()
        wa = monitor_work_area()
    except Exception as exc:
        return "dpi_debug 失败：%r" % (exc,)
    return "tid=%s 感知=%s 主屏=%.2f 鼠标屏=%.2f 工作区=%s" % (
        tid, dpi_awareness_name(), scale, pt, wa)


def dpi_scale():
    """返回主显示器缩放系数（1.0 = 96 DPI）。"""
    global _CACHED_DPI_SCALE
    if _CACHED_DPI_SCALE is not None:
        return _CACHED_DPI_SCALE
    scale = 1.0
    try:
        hdc = user32.GetDC(None)
        if hdc:
            LOGPIXELSX = 88
            dpi = gdi32.GetDeviceCaps(hdc, LOGPIXELSX)
            user32.ReleaseDC(None, hdc)
            if dpi:
                scale = dpi / 96.0
    except Exception:
        pass
    _CACHED_DPI_SCALE = max(1.0, min(scale, 4.0))
    return _CACHED_DPI_SCALE


def work_area(monitor_from_point=None):
    """返回主显示器工作区 (left, top, right, bottom)（已排除任务栏）。"""
    r = RECT()
    if user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
        return (r.left, r.top, r.right, r.bottom)
    return (0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))


def monitor_handle(x=0, y=0):
    """返回包含该点的显示器句柄（取最近的）。"""
    try:
        return user32.MonitorFromPoint(POINT(int(x), int(y)),
                                       MONITOR_DEFAULTTONEAREST)
    except Exception:
        return None


def monitor_work_area(x=0, y=0):
    """指定点所在显示器的工作区（多屏 + 每屏不同缩放时更准）。"""
    hmon = monitor_handle(x, y)
    if hmon:
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        try:
            if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right, r.bottom)
        except Exception:
            pass
    return work_area()


def dpi_scale_for_point(x=None, y=None):
    """指定显示器（默认鼠标所在屏）的缩放系数。

    多显示器各自缩放不同时，气泡要按"将出现的那块屏"来渲染，否则要么
    太小要么溢出。
    """
    if x is None or y is None:
        try:
            cx, cy = cursor_pos()
        except Exception:
            cx = cy = 0
        x, y = cx, cy
    scale = 0.0
    hmon = monitor_handle(x, y)
    if hmon and shcore is not None:
        dx = ctypes.c_uint(96)
        dy = ctypes.c_uint(96)
        try:
            if shcore.GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI,
                                       ctypes.byref(dx), ctypes.byref(dy)) == 0:
                scale = dx.value / 96.0
        except Exception:
            scale = 0.0
    if scale <= 0.0:
        scale = dpi_scale()
    return max(1.0, min(scale, 4.0))


def cursor_pos():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def get_desktop_path():
    """当前用户桌面目录（真实路径，OneDrive 重定向也能拿到）。"""
    try:
        path_ptr = ctypes.c_wchar_p()
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(FOLDERID_Desktop), 0,
                                          None, ctypes.byref(path_ptr))
        if hr == 0 and path_ptr.value:
            p = path_ptr.value
            ole32.CoTaskMemFree(path_ptr)
            if os.path.isdir(p):
                return p
    except Exception:
        pass
    cand = os.path.join(os.path.expanduser("~"), "Desktop")
    return cand


def get_downloads_path():
    """当前用户下载目录（用户在「属性 → 位置」里改过也能拿到）。

    优先使用 Windows 已知文件夹接口，它读取的是注册表里重定向后的真实位置；
    失败时退回 ``%USERPROFILE%\\Downloads``。返回的目录可能不存在，调用方需自行
    判断（下载位置被移到已拔出的 U 盘时就会这样）。
    """
    try:
        path_ptr = ctypes.c_wchar_p()
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(FOLDERID_Downloads), 0,
                                          None, ctypes.byref(path_ptr))
        if hr == 0 and path_ptr.value:
            p = path_ptr.value
            ole32.CoTaskMemFree(path_ptr)
            if p:
                return p
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Downloads")


def list_removable_drives():
    """返回所有可移动磁盘根目录，如 ['E:\\\\', 'F:\\\\']。"""
    buf = ctypes.create_unicode_buffer(512)
    n = kernel32.GetLogicalDriveStringsW(511, buf)
    roots = []
    if n:
        raw = buf[:n]
        for part in raw.split("\x00"):
            part = part.strip()
            if not part:
                continue
            root = part if part.endswith("\\") else part + "\\"
            if kernel32.GetDriveTypeW(root) == DRIVE_REMOVABLE:
                roots.append(root)
    return roots


def drive_type(root):
    return kernel32.GetDriveTypeW(root)


def load_icon_from_file(path, size=None):
    """从 .ico 载入 HICON；失败返回 None。"""
    flags = LR_LOADFROMFILE
    cx = cy = 0
    if size:
        cx = cy = size
    else:
        flags |= LR_DEFAULTSIZE
    h = user32.LoadImageW(None, path, IMAGE_ICON, cx, cy, flags)
    return h or None


# ------------------------------------------------------------- 开机自启动
def _run_key_open(write=False):
    hkey = wintypes.HKEY()
    disp = wintypes.DWORD()
    access = KEY_QUERY_VALUE | (KEY_SET_VALUE if write else 0)
    rc = advapi32.RegCreateKeyExW(HKEY_CURRENT_USER, RUN_KEY, 0, None, 0,
                                  access, None, ctypes.byref(hkey),
                                  ctypes.byref(disp))
    if rc != 0:
        return None
    return hkey


def autostart_value_name():
    return "classDesktopManager"


def set_autostart(enabled, command=None):
    hkey = _run_key_open(write=True)
    if not hkey:
        return False, "无法打开注册表启动项"
    try:
        name = autostart_value_name()
        if enabled:
            cmd = command or build_launch_command()
            data = ctypes.create_unicode_buffer(cmd)
            rc = advapi32.RegSetValueExW(hkey, name, 0, REG_SZ,
                                         ctypes.cast(data, ctypes.c_void_p),
                                         (len(cmd) + 1) * 2)
            if rc != 0:
                return False, "写入注册表失败 (code %d)" % rc
        else:
            advapi32.RegDeleteValueW(hkey, name)
        return True, ""
    finally:
        advapi32.RegCloseKey(hkey)


def get_autostart_command():
    hkey = _run_key_open(write=False)
    if not hkey:
        return None
    try:
        size = wintypes.DWORD(0)
        rc = advapi32.RegQueryValueExW(hkey, autostart_value_name(), None, None,
                                       None, ctypes.byref(size))
        if rc != 0 or size.value == 0:
            return None
        buf = ctypes.create_unicode_buffer(size.value // 2 + 2)
        rc = advapi32.RegQueryValueExW(hkey, autostart_value_name(), None, None,
                                       ctypes.cast(buf, ctypes.c_void_p),
                                       ctypes.byref(size))
        if rc != 0:
            return None
        return buf.value
    finally:
        advapi32.RegCloseKey(hkey)


def build_launch_command(extra_args="--tray"):
    """生成写入注册表的启动命令行。"""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        return '"%s" %s' % (exe, extra_args)
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.isfile(pyw):
        pyw = sys.executable
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "main.py"))
    return '"%s" "%s" %s' % (pyw, script, extra_args)


# --------------------------------------------------------------- 单实例
_MUTEX_NAME = "Local\\classDesktopManager.SingleInstance.v1"
_mutex_handle = None


def _mutex_name():
    # DSR_INSTANCE_SUFFIX 让自动化测试用独立互斥体，避免和老师正在用的实例互斥
    sfx = (os.environ.get("DSR_INSTANCE_SUFFIX") or "").strip()
    return _MUTEX_NAME + ("." + sfx if sfx else "")


def acquire_single_instance(name=None):
    """返回 True 表示本进程是唯一实例（name 仅供测试用独立互斥体）。"""
    global _mutex_handle
    h = kernel32.CreateMutexW(None, False, name or _mutex_name())
    if not h:
        return True
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        try:
            kernel32.CloseHandle(h)
        except Exception:
            pass
        return False
    _mutex_handle = h
    return True
