# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""路径与资源定位（兼容源码运行与 PyInstaller 打包运行）。"""
from __future__ import annotations

import os
import sys

APP_ID = "classDesktopManager"
APP_NAME = "classDesktopManager"
APP_VERSION = "1.7.0"
APP_DIR_NAME = "classDesktopManager"   # %APPDATA% 下的目录名（ASCII 更安全）


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def resource_root():
    """打包后资源解压目录 / 源码运行时项目根目录。"""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def asset_path(*parts):
    return os.path.join(resource_root(), "src", "dsr", "assets", *parts)


def assets_dir():
    return os.path.dirname(asset_path("x"))


def appdata_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, APP_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def config_path():
    return os.path.join(appdata_dir(), "config.json")


def log_path():
    return os.path.join(appdata_dir(), "app.log")


def history_path():
    return os.path.join(appdata_dir(), "history.json")


def install_dir():
    """程序所在目录（用于放置快捷方式 / 说明文件）。"""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def character_dir():
    return asset_path("characters")


def _variant_names():
    """所有作为「变体」出现的文件名（不出现在人物列表里）。"""
    out = set()
    for names in CHARACTER_VARIANTS.values():
        out.update(names[1:])
    return out


def builtin_characters():
    """返回 [(id, 显示名, png路径)]，按 CHARACTER_NAMES 的顺序排列。

    变体图（CHARACTER_VARIANTS 里第二个及之后的文件名）不会单独出现，
    它们只在角色被选中时参与轮换。
    """
    d = character_dir()
    skip = _variant_names()
    found = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.startswith("_") or not fn.lower().endswith(".png"):
                continue
            cid = os.path.splitext(fn)[0]
            if cid in skip:
                continue
            found[cid] = os.path.join(d, fn)
    order = list(CHARACTER_NAMES.keys()) + [k for k in found
                                            if k not in CHARACTER_NAMES]
    return [(cid, CHARACTER_NAMES.get(cid, cid), found[cid])
            for cid in order if cid in found]


def character_files(cid):
    """某个形象可用的全部立绘路径（含变体，按轮换顺序），可能为空。"""
    d = character_dir()
    names = CHARACTER_VARIANTS.get(cid, (cid,))
    out = []
    for n in names:
        p = os.path.join(d, n + ".png")
        if os.path.isfile(p):
            out.append(p)
    if not out:
        p = os.path.join(d, (cid or "") + ".png")
        if os.path.isfile(p):
            out.append(p)
    return out


CHARACTER_NAMES = {
    "teacher_f": "小语老师（青）",
    "teacher_m": "小博老师（蓝）",
    "teacher_nene": "绫宁宁（紫）",
    "teacher_miku": "初音未来（青绿）",
}

# 同一形象配多张立绘时，每弹一次气泡换一张（顺序即轮换顺序）。
CHARACTER_VARIANTS = {
    "teacher_nene": ("teacher_nene", "teacher_nene_2"),
}
