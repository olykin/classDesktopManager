# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""界面公共部分：DPI 缩放、窗口居中、配色、小控件。"""
from __future__ import annotations

import tkinter as tk

from . import winapi

# 进程已声明为 DPI 感知，Tk 的字号（点）会按真实 DPI 放大；
# 这里把界面里的"像素"数值统一乘上同一个系数，保证比例一致。
S = float(winapi.dpi_scale() or 1.0)
if S < 1.0:
    S = 1.0


def px(v):
    """把设计稿像素换算成当前 DPI 下的实际像素。"""
    return int(round(float(v) * S))


def center(win, w, h, bias=3):
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // bias)
    win.geometry("%dx%d+%d+%d" % (w, h, x, y))


BG = "#EEF2F7"
CARD = "#FFFFFF"
SOFT = "#F8FAFC"
BORDER = "#DCE3EC"
TEXT = "#1F2937"
MUTED = "#6B7280"
ACCENT = "#2B6CB0"
ACCENT_D = "#22518A"
OK = "#2F855A"
WARN = "#B7791F"
DANGER = "#C53030"
FONT = "Microsoft YaHei UI"


def font(size, bold=False):
    return (FONT, size, "bold") if bold else (FONT, size)


def short_path(path, keep=34):
    """路径太长时中间省略，避免撑破界面。"""
    if not path or len(path) <= keep:
        return path or "-"
    head = path[:max(6, keep // 2 - 2)]
    tail = path[-(keep - len(head) - 3):]
    return "%s...%s" % (head, tail)


class ScrollFrame(tk.Frame):
    """可竖向滚动的容器：把内容放进 ``.body``。"""

    def __init__(self, master, bg=BG, **kw):
        super().__init__(master, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(self, orient="vertical",
                                command=self.canvas.yview, relief="flat",
                                bd=0, width=px(12))
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=bg)
        self._wid = self.canvas.create_window((0, 0), window=self.body,
                                              anchor="nw")
        self.body.bind("<Configure>", self._on_body)
        self.canvas.bind("<Configure>", self._on_canvas)

    def _on_body(self, _e=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, ev):
        self.canvas.itemconfigure(self._wid, width=ev.width)

    def on_wheel(self, ev):
        try:
            first, last = self.canvas.yview()
            if first <= 0.0 and last >= 1.0:
                return
            self.canvas.yview_scroll(int(-ev.delta / 120), "units")
        except Exception:
            pass
