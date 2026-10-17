# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""一个专用的 Win32 消息线程。

托盘图标和气泡窗口都必须在同一个拥有消息循环的线程上创建，
而 tkinter 又必须占用主线程，所以这里开一个后台线程跑消息泵，
其它线程通过 ``post()`` 把任务丢进来执行。
"""
from __future__ import annotations

import collections
import ctypes
import threading
from ctypes import wintypes

from . import winapi


class UiThread(threading.Thread):
    """后台 Win32 消息线程。"""

    WM_RUN = winapi.WM_APP + 2

    def __init__(self, setup=None, on_error=None, name="dsr-ui"):
        super().__init__(name=name, daemon=True)
        self._setup = setup
        self._on_error = on_error
        self._pending = collections.deque()
        self._lock = threading.Lock()
        self._tid = None
        self.ready = threading.Event()
        self._stopping = False
        self.obj = None          # setup() 的返回值，供调用方取用
        self.error = None

    # ------------------------------------------------------------ 线程内
    def run(self):
        try:
            self._tid = winapi.kernel32.GetCurrentThreadId()
            # 强制为本线程创建消息队列，之后 PostThreadMessageW 才有效
            msg = winapi.MSG()
            winapi.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0,
                                       winapi.PM_NOREMOVE)
            if self._setup is not None:
                self.obj = self._setup(self)
            self.ready.set()
            self._pump()
        except Exception as exc:                       # pragma: no cover
            self.error = exc
            self.ready.set()
            if self._on_error:
                try:
                    self._on_error(exc)
                except Exception:
                    pass
        finally:
            self._tid = None

    def _pump(self):
        msg = winapi.MSG()
        while True:
            r = winapi.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if r <= 0:
                break
            if msg.message == self.WM_RUN:
                self._drain()
                continue
            winapi.user32.TranslateMessage(ctypes.byref(msg))
            winapi.user32.DispatchMessageW(ctypes.byref(msg))
        self._drain()

    def _drain(self):
        while True:
            with self._lock:
                if not self._pending:
                    return
                fn = self._pending.popleft()
            try:
                fn()
            except Exception as exc:                   # pragma: no cover
                if self._on_error:
                    try:
                        self._on_error(exc)
                    except Exception:
                        pass

    # ---------------------------------------------------------- 线程间
    def post(self, fn):
        """把 fn 排到 UI 线程执行（非阻塞、线程安全）。"""
        with self._lock:
            self._pending.append(fn)
        tid = self._tid
        if tid:
            winapi.user32.PostThreadMessageW(tid, self.WM_RUN, 0, 0)

    def call(self, fn, timeout=5.0):
        """在 UI 线程同步执行 fn 并等待结果。"""
        box = {}
        done = threading.Event()

        def wrapper():
            try:
                box["r"] = fn()
            except Exception as exc:
                box["e"] = exc
            finally:
                done.set()

        if threading.current_thread() is self:
            return fn()
        self.post(wrapper)
        if not done.wait(timeout):
            return None
        if "e" in box:
            raise box["e"]
        return box.get("r")

    def stop(self, timeout=2.0):
        if self._stopping:
            return
        self._stopping = True
        tid = self._tid
        if tid:
            winapi.user32.PostThreadMessageW(tid, 0x0012, 0, 0)   # WM_QUIT
        if threading.current_thread() is not self:
            self.join(timeout)


# WPARAM/LPARAM 辅助
WPARAM = wintypes.WPARAM
LPARAM = wintypes.LPARAM
