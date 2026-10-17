# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""枚举所有 DsrBubbleWnd / DsrTrayWnd 顶层窗口，打印 hwnd / pid / 进程名 / 矩形。

用途：排查「exe 里的气泡窗口尺寸与预期不符」时，确认到底有几个气泡窗口、
分别属于哪个进程。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                     wintypes.LPARAM)

WANT = ("DsrBubbleWnd", "DsrTrayWnd")


def class_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def title_of(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    u32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def pid_of(hwnd):
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def proc_name(pid):
    h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return "?"
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value)
    finally:
        k32.CloseHandle(h)
    return "?"


def scan():
    """枚举窗口。

    调用方必须先声明 DPI 感知（``winapi.set_dpi_awareness()``），否则
    GetWindowRect 返回的是被系统虚拟化过的坐标，在 4K@250% 下会缩小 2.5 倍。
    """
    out = []

    def cb(hwnd, _lparam):
        cls = class_of(hwnd)
        if cls in WANT:
            rc = wintypes.RECT()
            u32.GetWindowRect(hwnd, ctypes.byref(rc))
            pid = pid_of(hwnd)
            out.append((cls, hwnd, pid, proc_name(pid),
                        (rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top),
                        bool(u32.IsWindowVisible(hwnd))))
        return True

    u32.EnumWindows(EnumWindowsProc(cb), 0)
    return out


def main():
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "src"))
        from dsr import winapi
        winapi.set_dpi_awareness()
    except Exception as exc:
        print("警告：DPI 感知设置失败 %r" % (exc,), flush=True)
    for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 1):
        rows = scan()
        print("--- %s  共 %d 个窗口" % (time.strftime("%H:%M:%S"), len(rows)),
              flush=True)
        for cls, hwnd, pid, name, rect, vis in rows:
            print("  %-14s hwnd=%-8s pid=%-6s %-32s rect=%s visible=%s"
                  % (cls, hwnd, pid, name, rect, vis), flush=True)
        time.sleep(1.0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
