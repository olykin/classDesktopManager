# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""可移动磁盘（U 盘）文件检索。

用途：判断桌面新出现的文件是否来自 U 盘。
策略：在可移动磁盘上按“同名 + 同大小”查找源文件，命中即认定来自 U 盘。
带缓存与时间预算，避免拖慢主流程。
"""
from __future__ import annotations

import os
import threading
import time

from . import winapi

SKIP_DIRS = {
    "$RECYCLE.BIN", "System Volume Information", ".Trash", ".Trashes",
    "$WinREAgent", "Config.Msi", "Recovery",
}

_cache_lock = threading.Lock()
# root -> (timestamp, {(lowername, size): path})
_index_cache = {}
CACHE_TTL = 180.0


def removable_roots():
    return [r for r in winapi.list_removable_drives() if os.path.isdir(r)]


def _index_drive(root, budget=6.0, max_entries=120000):
    """索引一个磁盘（广度优先，有深度与条目上限）。"""
    t0 = time.time()
    index = {}
    queue = [(root, 0)]
    count = 0
    while queue:
        if time.time() - t0 > budget or count > max_entries:
            break
        path, depth = queue.pop(0)
        try:
            with os.scandir(path) as it:
                for entry in it:
                    count += 1
                    if count > max_entries:
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if depth < 4 and entry.name not in SKIP_DIRS \
                                    and not entry.name.startswith("."):
                                queue.append((entry.path, depth + 1))
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            key = (entry.name.lower(), st.st_size)
                            index.setdefault(key, entry.path)
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue
    return index


def _get_index(root, force=False):
    now = time.time()
    with _cache_lock:
        hit = _index_cache.get(root)
        if hit and not force and now - hit[0] < CACHE_TTL:
            return hit[1]
    idx = _index_drive(root)
    with _cache_lock:
        _index_cache[root] = (time.time(), idx)
    return idx


def invalidate(root=None):
    with _cache_lock:
        if root is None:
            _index_cache.clear()
        else:
            _index_cache.pop(root, None)


def find_source(name, size):
    """在所有可移动磁盘上查找同名同大小的文件。

    返回 (磁盘根目录, 完整路径) 或 (None, None)。
    """
    if not name:
        return None, None
    key = (name.lower(), int(size))
    for root in removable_roots():
        idx = _get_index(root)
        hit = idx.get(key)
        if hit and os.path.isfile(hit):
            return root, hit
        # 缓存可能过期，强制重建一次
        idx = _get_index(root, force=True)
        hit = idx.get(key)
        if hit and os.path.isfile(hit):
            return root, hit
    return None, None


def drive_label(root):
    try:
        return root.rstrip("\\")
    except Exception:
        return root
