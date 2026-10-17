# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""系统托盘图标（Shell_NotifyIcon），必须在带消息循环的线程上创建。"""
from __future__ import annotations

import ctypes

from . import winapi

user32 = winapi.user32
shell32 = winapi.shell32

_CLASS = "DsrTrayWnd"
_atom = None
_wndproc_ref = None
_instances = {}

TRAY_ID = 1


def _wndproc(hwnd, msg, wparam, lparam):
    tray = _instances.get(int(hwnd or 0))
    if tray is None:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    try:
        return tray.on_message(msg, wparam, lparam)
    except Exception:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def ensure_class():
    global _atom, _wndproc_ref
    if _atom:
        return _atom
    hinst = winapi.kernel32.GetModuleHandleW(None)
    _wndproc_ref = winapi.WNDPROC(_wndproc)
    wc = winapi.WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(winapi.WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = _wndproc_ref
    wc.hInstance = hinst
    wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(winapi.IDC_ARROW_))
    wc.hbrBackground = None
    wc.lpszClassName = _CLASS
    _atom = user32.RegisterClassExW(ctypes.byref(wc))
    return _atom


class TrayIcon:
    """托盘图标 + 单击菜单。"""

    def __init__(self, icon_path=None, tooltip="classDesktopManager",
                 on_command=None):
        self.icon_path = icon_path
        self.tooltip = tooltip
        self.on_command = on_command
        self.hwnd = None
        self.hicon = None
        self._added = False
        self._paused = False

    # ------------------------------------------------------------ 生命周期
    def create(self):
        ensure_class()
        hinst = winapi.kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            winapi.WS_EX_TOOLWINDOW, _CLASS, "DsrTray", winapi.WS_POPUP,
            0, 0, 0, 0, None, None, hinst, None)
        if not self.hwnd:
            raise OSError("创建托盘窗口失败")
        _instances[int(self.hwnd)] = self
        self._load_icon()
        self._add()
        return self

    def _load_icon(self):
        size = user32.GetSystemMetrics(winapi.SM_CXSMICON) or 16
        h = None
        if self.icon_path:
            h = winapi.load_icon_from_file(self.icon_path, size)
        self.hicon = h or user32.LoadIconW(None,
                                           ctypes.c_void_p(winapi.IDI_APPLICATION))

    def set_icon(self, path):
        self.icon_path = path
        old = self.hicon
        self._load_icon()
        if self._added:
            nid = self._nid(winapi.NIF_ICON)
            shell32.Shell_NotifyIconW(winapi.NIM_MODIFY, ctypes.byref(nid))

    def _nid(self, flags):
        nid = winapi.NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(winapi.NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = TRAY_ID
        nid.uFlags = flags
        nid.uCallbackMessage = winapi.WM_TRAYICON
        nid.hIcon = self.hicon
        nid.szTip = self.tooltip[:127]
        return nid

    def _add(self):
        nid = self._nid(winapi.NIF_MESSAGE | winapi.NIF_ICON | winapi.NIF_TIP)
        ok = shell32.Shell_NotifyIconW(winapi.NIM_ADD, ctypes.byref(nid))
        self._added = bool(ok)
        return self._added

    def destroy(self):
        if self._added and self.hwnd:
            nid = self._nid(0)
            shell32.Shell_NotifyIconW(winapi.NIM_DELETE, ctypes.byref(nid))
            self._added = False
        if self.hwnd:
            _instances.pop(int(self.hwnd), None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    # ---------------------------------------------------------------- 状态
    def set_tooltip(self, text):
        self.tooltip = text
        if self._added:
            shell32.Shell_NotifyIconW(winapi.NIM_MODIFY,
                                      ctypes.byref(self._nid(winapi.NIF_TIP)))

    def set_paused(self, paused):
        self._paused = bool(paused)
        self.set_tooltip("classDesktopManager（已暂停）" if paused
                         else "classDesktopManager（运行中）")

    def notify(self, title, text):
        """气泡通知（系统托盘提示）。"""
        if not self._added:
            return
        nid = self._nid(winapi.NIF_INFO)
        nid.szInfoTitle = (title or "")[:63]
        nid.szInfo = (text or "")[:255]
        nid.dwInfoFlags = 0x00000001  # NIIF_INFO
        shell32.Shell_NotifyIconW(winapi.NIM_MODIFY, ctypes.byref(nid))

    # ---------------------------------------------------------------- 菜单
    def _show_menu(self):
        menu = user32.CreatePopupMenu()
        if not menu:
            return
        try:
            user32.AppendMenuW(menu, winapi.MF_STRING, winapi.IDM_SHOW,
                               "打开主界面(&M)")
            user32.AppendMenuW(menu, winapi.MF_STRING, winapi.IDM_SETTINGS,
                               "设置(&S)")
            user32.AppendMenuW(menu, winapi.MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, winapi.MF_STRING, winapi.IDM_CHECK,
                               "立即检测桌面(&C)")
            user32.AppendMenuW(menu, winapi.MF_STRING, winapi.IDM_OPEN_DESKTOP,
                               "打开桌面文件夹(&D)")
            flags = winapi.MF_STRING | (winapi.MF_CHECKED if self._paused else 0)
            user32.AppendMenuW(menu, flags, winapi.IDM_PAUSE,
                               "暂停提醒(&P)" if not self._paused else "继续提醒(&P)")
            user32.AppendMenuW(menu, winapi.MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, winapi.MF_STRING, winapi.IDM_EXIT,
                               "退出软件(&X)")
            x, y = winapi.cursor_pos()
            user32.SetForegroundWindow(self.hwnd)
            cmd = user32.TrackPopupMenu(
                menu,
                winapi.TPM_RIGHTBUTTON | winapi.TPM_RETURNCMD |
                winapi.TPM_NONOTIFY | winapi.TPM_LEFTALIGN,
                x, y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, winapi.WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
        if cmd and self.on_command:
            self.on_command(int(cmd))

    # ---------------------------------------------------------------- 消息
    def on_message(self, msg, wparam, lparam):
        if msg == winapi.WM_TRAYICON:
            ev = lparam & 0xFFFF
            if ev in (winapi.WM_LBUTTONUP, winapi.WM_RBUTTONUP):
                self._show_menu()
            elif ev == winapi.WM_LBUTTONDBLCLK:
                if self.on_command:
                    self.on_command(winapi.IDM_SHOW)
            return 0
        if msg == winapi.WM_DESTROY:
            _instances.pop(int(self.hwnd or 0), None)
            return 0
        return user32.DefWindowProcW(self.hwnd, msg, wparam, lparam)
