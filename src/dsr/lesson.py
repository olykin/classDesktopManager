# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""ClassIsland 课程联动：读取插件写的本地快照。

ClassIsland 插件（classisland-plugin）会在上课状态变化时，把当前课程写到
``%APPDATA%\\classDesktopManager\\classisland.json``，每 10 秒刷新一次心跳。
本模块只做只读解析，任何异常都退化为「没有课程信息」，绝不影响归档主流程。
"""
from __future__ import annotations

import json
import os
import time

from . import paths

SNAPSHOT_NAME = "classisland.json"
SCHEMA = 1
DEFAULT_MAX_AGE = 60  # 秒；超过这个时间没更新就当作 ClassIsland 已退出


def snapshot_path():
    return os.path.join(paths.appdata_dir(), SNAPSHOT_NAME)


def read_raw(max_age=DEFAULT_MAX_AGE):
    """读取快照原始字典；文件缺失、损坏或过期时返回 None。"""
    path = snapshot_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    try:
        updated = float(data.get("updated") or 0)
    except (TypeError, ValueError):
        return None
    if updated <= 0 or time.time() - updated / 1000.0 > max_age:
        return None
    return data


def current(max_age=DEFAULT_MAX_AGE):
    """当前正在上的课。

    返回 ``{"subject": "数学", "state": "OnClass", "next": "语文"}``；
    不在上课、没有科目或快照过期时返回 None。
    """
    data = read_raw(max_age)
    if not data:
        return None
    subject = str(data.get("subject") or "").strip()
    if not subject or not data.get("onClass"):
        return None
    return {
        "subject": subject,
        "state": str(data.get("state") or ""),
        "next": str(data.get("nextSubject") or "").strip(),
    }


def describe(max_age=DEFAULT_MAX_AGE):
    """给设置界面用的一行状态说明。"""
    data = read_raw(max_age)
    if not data:
        if os.path.exists(snapshot_path()):
            return "快照已过期（ClassIsland 可能没在运行）"
        return "未连接：请先安装并启动 ClassIsland 与配套插件"
    subject = str(data.get("subject") or "").strip()
    state = str(data.get("state") or "")
    if data.get("onClass") and subject:
        return "当前课程：%s（%s）" % (subject, state or "OnClass")
    if subject:
        return "当前不是上课时间（%s，最近科目 %s）" % (state or "未知", subject)
    return "已连接 ClassIsland（%s，暂无课程）" % (state or "无状态")
