# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""桌面目录监视：轮询发现"新出现的文件"，等文件大小稳定后再上报。

只监视桌面**根目录**，不递归子文件夹（子文件夹正是老师最终要放的位置）。
"""
from __future__ import annotations

import os
import threading
import time

from . import config

IGNORE_SUFFIX = (
    ".tmp", ".temp", ".part", ".crdownload", ".partial", ".download",
    ".!ut", ".bak~",
)
IGNORE_PREFIX = ("~$", "~", ".", "$")


def _is_candidate(name):
    low = name.lower()
    if low == "desktop.ini" or low == "thumbs.db":
        return False
    if low.endswith(IGNORE_SUFFIX):
        return False
    # 快捷方式永远不提醒：老师桌面上通常有一大堆 .lnk
    if config.is_shortcut(name):
        return False
    for p in IGNORE_PREFIX:
        if name.startswith(p):
            return False
    return True


class DesktopWatcher(threading.Thread):
    """后台线程，轮询桌面目录。"""

    def __init__(self, desktop_path, interval=1.0, on_new_file=None,
                 on_error=None):
        super().__init__(name="DesktopWatcher", daemon=True)
        self.desktop_path = desktop_path
        self.interval = max(0.3, float(interval))
        self.on_new_file = on_new_file
        self.on_error = on_error

        self._stop = threading.Event()
        self.paused = False
        self._known = {}          # name -> (size, mtime)
        self._pending = {}        # name -> {"size":.., "mtime":.., "hit":int, "first":ts}
        self.primes_done = threading.Event()

    # ------------------------------------------------------------- 控制
    def stop(self):
        self._stop.set()

    def set_paused(self, paused):
        self.paused = bool(paused)

    def set_interval(self, interval):
        self.interval = max(0.3, float(interval))

    def rescan(self, desktop_path=None):
        """重新建立基线（切桌面路径 / 恢复监控后调用）。"""
        if desktop_path:
            self.desktop_path = desktop_path
        self._known = self._snapshot()
        self._pending.clear()

    def set_desktop(self, desktop_path):
        self.rescan(desktop_path)

    # ------------------------------------------------------------- 内部
    def _snapshot(self):
        out = {}
        try:
            with os.scandir(self.desktop_path) as it:
                for entry in it:
                    try:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                    except OSError:
                        continue
                    if not _is_candidate(entry.name):
                        continue
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    out[entry.name] = (st.st_size, st.st_mtime)
        except Exception as e:  # noqa: BLE001
            if self.on_error:
                self.on_error(e)
        return out

    def _emit(self, name, size, mtime):
        path = os.path.join(self.desktop_path, name)
        try:
            if self.on_new_file:
                self.on_new_file(path, size, mtime)
        except Exception:  # noqa: BLE001
            pass

    def run(self):
        self._known = self._snapshot()
        self.primes_done.set()
        while not self._stop.wait(self.interval):
            if self.paused:
                self._known = self._snapshot()
                self._pending.clear()
                continue
            current = self._snapshot()
            now = time.time()

            # 1. 发现新名字
            for name, (size, mtime) in current.items():
                if name not in self._known and name not in self._pending:
                    self._pending[name] = {"size": size, "mtime": mtime,
                                           "hit": 0, "first": now, "notified": False}

            # 2. 已消失的文件不再等待
            for name in list(self._pending.keys()):
                if name not in current:
                    self._pending.pop(name, None)

            # 3. 稳定性判定
            for name, info in list(self._pending.items()):
                if name not in current:
                    continue
                size, mtime = current[name]
                if (size, mtime) == (info["size"], info["mtime"]):
                    info["hit"] += 1
                else:
                    info["size"], info["mtime"] = size, mtime
                    info["hit"] = 0

                waited = now - info["first"]
                ready = info["hit"] >= 2 or (info["hit"] >= 1 and waited > 6)
                give_up = waited > 300
                if (ready and size > 0) or give_up:
                    if not info["notified"]:
                        info["notified"] = True
                        self._emit(name, size, mtime)
                    self._pending.pop(name, None)

            self._known = current


def desktop_snapshot(path):
    return DesktopWatcher(path)._snapshot()
