# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""气泡按钮"点不动"的诊断：直接问操作系统这个点会命中哪个窗口。"""
from __future__ import annotations

import ctypes
import os
import sys
import time
from ctypes import wintypes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dsr import bubble, paths, uithread, winapi  # noqa: E402

u32 = ctypes.windll.user32
u32.WindowFromPoint.argtypes = [winapi.POINT]
u32.WindowFromPoint.restype = wintypes.HWND
u32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
u32.GetClassNameW.restype = ctypes.c_int


def cls_of(hwnd):
    if not hwnd:
        return "<null>"
    buf = ctypes.create_unicode_buffer(256)
    u32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def main():
    winapi.set_dpi_awareness()
    fired = []
    state = {}

    def setup(ui):
        return bubble.BubbleManager(scale=winapi.dpi_scale())

    ui = uithread.UiThread(setup)
    ui.start()
    if not ui.ready.wait(6):
        print("UiThread 启动失败", flush=True)
        return 1
    bm = ui.obj

    spec = {
        "title": "老师好呀，发现一个新文件",
        "body": ["《第三单元数学测试卷.docx》", "大小 2.0 KB · 来自 桌面"],
        "hint": "建议归档到「数学」文件夹 · 文件名包含「数学」",
        "accent": "#2E7D5B",
        "character_path": paths.builtin_characters()[0][2],
        "buttons": [{"id": "move", "text": "移动到「数学」", "kind": "primary"},
                    {"id": "other", "text": "放置在其他文件夹", "kind": "ghost"},
                    {"id": "later", "text": "稍后处理", "kind": "ghost"}],
    }
    win = ui.call(lambda: bm.show(
        spec, corner="br", duration=90.0,
        on_action=lambda aid, w: fired.append(aid)), timeout=10)
    state["win"] = win
    time.sleep(0.8)

    hwnd = win.hwnd
    print("气泡 hwnd = %s  class=%s" % (hwnd, cls_of(hwnd)), flush=True)
    print("bubble hwnd = %s" % win.hwnd, flush=True)

    lay = win.layout
    x0w, y0w = win.x, win.y
    print("窗口位置 = (%d, %d)  尺寸 = %dx%d" % (x0w, y0w, win.width, win.height),
          flush=True)
    print("layout.buttons = %s" % (lay.buttons,), flush=True)
    print("layout.close_rect = %s" % (lay.close_rect,), flush=True)

    print("\n%-10s %-22s %-10s %-12s %-14s %s" % (
        "按钮", "中心(屏幕)", "NCHITTEST", "命中窗口类", "是本窗口?", "命中窗口hwnd"),
        flush=True)
    for (bx0, by0, bx1, by1, bid, kind) in lay.buttons:
        cx = int((bx0 + bx1) // 2)
        cy = int((by0 + by1) // 2)
        sx, sy = x0w + cx, y0w + cy
        lparam = ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)
        ht = u32.SendMessageW(hwnd, winapi.WM_NCHITTEST, 0, lparam)
        hit = u32.WindowFromPoint(winapi.POINT(sx, sy))
        print("%-10s (%4d,%4d)        %-10s %-12s %-14s %s" % (
            bid, sx, sy, ht, cls_of(hit), hit == hwnd, hit), flush=True)

    # 再模拟一次完整点击，看动作有没有触发
    print("\n模拟点击:", flush=True)
    for (bx0, by0, bx1, by1, bid, kind) in lay.buttons:
        cx = int((bx0 + bx1) // 2)
        cy = int((by0 + by1) // 2)
        lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
        u32.SendMessageW(hwnd, winapi.WM_MOUSEMOVE, 0, lp)
        time.sleep(0.05)
        u32.SendMessageW(hwnd, winapi.WM_LBUTTONDOWN, 1, lp)
        time.sleep(0.05)
        u32.SendMessageW(hwnd, winapi.WM_LBUTTONUP, 0, lp)
        time.sleep(0.15)
        print("  点击 %-8s -> fired=%s" % (bid, fired), flush=True)

    ui.call(lambda: bm.close_all(), timeout=5)
    ui.stop()
    print("\nfired 汇总 = %s" % fired, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
