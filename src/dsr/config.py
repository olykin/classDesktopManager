# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""配置读写与科目建议算法。"""
from __future__ import annotations

import json
import os
import re
import threading

from . import paths

_LOCK = threading.RLock()

# 常见科目及其关键词（用于从文件名猜科目）
DEFAULT_KEYWORDS = {
    "语文": ["语文", "作文", "周记", "日记", "阅读", "古诗", "生字", "听写", "拼音", "文学", "课文"],
    "数学": ["数学", "口算", "计算", "几何", "代数", "方程", "奥数", "应用题", "试卷"],
    "英语": ["英语", "english", "单词", "听力", "语法", "reading", "phonics", "音标"],
    "物理": ["物理", "力学", "电学"],
    "化学": ["化学", "方程式"],
    "生物": ["生物", "细胞"],
    "道德与法治": ["道法", "道德", "法治", "政治"],
    "历史": ["历史"],
    "地理": ["地理"],
    "科学": ["科学", "实验"],
    "音乐": ["音乐", "歌曲", "儿歌", "合唱", "乐谱"],
    "美术": ["美术", "画画", "绘画", "手工", "书法"],
    "体育": ["体育", "运动", "体操", "广播操"],
    "信息技术": ["信息技术", "信息", "编程", "电脑", "课件"],
    "课件教案": ["课件", "教案", "教学设计", "说课", "反思"],
    "作业": ["作业", "练习", "习题"],
    "通知文件": ["通知", "公告", "文件", "方案", "计划", "总结"],
    "照片": ["照片", "图片", "合影", "相册"],
}

# 扩展名兜底建议（仅在对应文件夹存在时生效）
EXT_SUBJECT = {
    ".mp3": "音乐", ".wav": "音乐", ".flac": "音乐", ".m4a": "音乐", ".wma": "音乐",
    ".mp4": "视频", ".avi": "视频", ".mkv": "视频", ".mov": "视频", ".wmv": "视频",
    ".jpg": "照片", ".jpeg": "照片", ".png": "照片", ".bmp": "照片", ".gif": "照片",
}

# ------------------------------------------------------------------ 文件分类
# 「快捷方式」永远不提醒：老师桌面上一定有大量 .lnk，提醒它们纯属打扰。
SHORTCUT_EXT = {
    ".lnk", ".url", ".pif", ".website", ".desktop", ".scf", ".job",
    ".appref-ms", ".msc", ".webloc", ".xnk", ".lnk2",
}

# 办公文档：软件的主要关注对象
OFFICE_EXT = {
    ".doc", ".docx", ".docm", ".dot", ".dotx", ".rtf", ".txt", ".md",
    ".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".csv", ".tsv",
    ".ppt", ".pptx", ".pptm", ".pot", ".potx", ".pps", ".ppsx",
    ".pdf", ".odt", ".ods", ".odp", ".odg", ".wps", ".et", ".dps",
    ".one", ".vsd", ".vsdx", ".pub", ".mpp", ".xmind", ".mm", ".wpd",
    ".pages", ".numbers", ".key", ".hwp", ".caj", ".epub", ".mobi",
}

# 图片：软件的另一个主要关注对象
IMAGE_EXT = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".gif", ".webp",
    ".tif", ".tiff", ".heic", ".heif", ".avif", ".ico", ".svg", ".raw",
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".psd",
    ".ai", ".cdr", ".wmf", ".emf", ".xcf", ".sketch", ".fig",
}

MEDIA_EXT = {
    ".mp3", ".wav", ".flac", ".m4a", ".wma", ".aac", ".ogg", ".ape",
    ".mid", ".midi", ".amr", ".opus",
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    ".mpg", ".mpeg", ".rmvb", ".rm", ".ts", ".3gp", ".vob", ".f4v",
}

ARCHIVE_EXT = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".zst",
    ".iso", ".cab", ".lzh", ".arj", ".jar", ".apk", ".dmg",
}

# 文件大类 -> 显示名
KIND_LABELS = {
    "shortcut": "快捷方式",
    "office": "办公文档",
    "image": "图片",
    "media": "音视频",
    "archive": "压缩包",
    "program": "程序/安装包",
    "other": "其他",
}

PROGRAM_EXT = {
    ".exe", ".msi", ".bat", ".cmd", ".com", ".scr", ".ps1", ".vbs",
    ".reg", ".dll", ".sys", ".inf", ".msu", ".appx", ".msix",
}

# 设置界面里可勾选的「关注的文件类型」（快捷方式永远不关注，故不在列表里）
AUTO_KIND_CHOICES = [
    ("office", "办公文档（Word / Excel / PPT / PDF / 文本）"),
    ("image", "图片（照片 / 截图 / 扫描件）"),
    ("media", "音视频（录音 / 录像）"),
    ("archive", "压缩包"),
    ("program", "程序与安装包"),
    ("other", "其他文件"),
]

DEFAULT_SUBJECTS = ["语文", "数学", "英语", "科学", "道德与法治", "音乐", "美术", "体育"]

DEFAULTS = {
    "version": 1,
    "autostart": False,
    "start_minimized": True,
    "close_to_tray": True,
    "sound": True,
    "character": "teacher_f",
    "corner": "br",              # br / bl / tr / tl
    "duration": 14,              # 气泡停留秒数
    "detect_mode": "smart",      # usb / smart / all
    "show_move_button": True,    # 是否显示"移动到"按钮
    "show_open_button": True,
    "watch_interval": 1.0,
    "paused": False,
    "subjects": [],              # [{"name": "...", "keywords": [...]}]
    "auto_kinds": ["office", "image"],   # 自动关注的文件大类
    "ask_unknown": True,         # 认不出科目时弹气泡询问放哪个文件夹
    "ext_subjects": {},          # {".xlsx": "数学"} 老师亲自指定过的类型映射
    "first_run": True,
    "desktop_path": "",          # 留空表示自动检测
}

_CJK = re.compile(r"[\u3000-\u9fff\uf900-\ufaff]")


# ------------------------------------------------------------------ 读写
def _merge_defaults(data):
    cfg = dict(DEFAULTS)
    if isinstance(data, dict):
        for k, v in data.items():
            if k in DEFAULTS:
                cfg[k] = v
        # 保留未知键，避免升级时丢数据
        for k, v in data.items():
            cfg.setdefault(k, v)
    return cfg


def load():
    with _LOCK:
        path = paths.config_path()
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        cfg = _merge_defaults(data)
        if not cfg.get("subjects"):
            cfg["subjects"] = build_default_subjects(cfg.get("desktop_path") or None)
        return cfg


def save(cfg):
    with _LOCK:
        path = paths.config_path()
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True, ""
        except Exception as e:  # noqa: BLE001
            return False, str(e)


# --------------------------------------------------------------- 科目列表
def normalize_subject(entry):
    """把字符串或 dict 统一成 {"name":..., "keywords":[...]}。"""
    if isinstance(entry, str):
        name = entry.strip()
        kws = list(DEFAULT_KEYWORDS.get(name, []))
        if name and name not in kws:
            kws.insert(0, name)
        return {"name": name, "keywords": kws}
    name = str(entry.get("name", "")).strip()
    kws = [str(k).strip() for k in entry.get("keywords", []) if str(k).strip()]
    if name and name not in kws:
        kws.insert(0, name)
    return {"name": name, "keywords": kws}


def build_default_subjects(desktop_path=None):
    """优先采用桌面上真实存在的子文件夹作为科目文件夹。"""
    names = []
    d = desktop_path or paths_os_desktop()
    try:
        for entry in sorted(os.listdir(d)):
            full = os.path.join(d, entry)
            if os.path.isdir(full) and not entry.startswith(".") \
                    and not entry.startswith("$") and entry.lower() != "desktop.ini":
                names.append(entry)
    except Exception:
        pass
    if not names:
        names = list(DEFAULT_SUBJECTS)
    return [normalize_subject(n) for n in names]


def paths_os_desktop():
    from . import winapi
    return winapi.get_desktop_path()


def subject_names(cfg):
    return [s["name"] for s in cfg.get("subjects", []) if s.get("name")]


def subject_exists(cfg, name):
    if not name:
        return False
    desktop = cfg.get("desktop_path") or paths_os_desktop()
    return os.path.isdir(os.path.join(desktop, name))


# --------------------------------------------------------------- 文件分类
def file_ext(filename):
    return os.path.splitext(filename or "")[1].lower()


def is_shortcut(filename):
    """快捷方式（.lnk / .url / …）——永远不提醒。"""
    return file_ext(filename) in SHORTCUT_EXT


def file_kind(filename):
    """把文件归入一个大类：office / image / media / archive / program /
    shortcut / other。"""
    ext = file_ext(filename)
    if ext in SHORTCUT_EXT:
        return "shortcut"
    if ext in OFFICE_EXT:
        return "office"
    if ext in IMAGE_EXT:
        return "image"
    if ext in MEDIA_EXT:
        return "media"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in PROGRAM_EXT:
        return "program"
    return "other"


def kind_label(kind):
    return KIND_LABELS.get(kind, kind or "其他")


def auto_kinds(cfg):
    """当前关注的文件大类。"""
    kinds = cfg.get("auto_kinds")
    if not isinstance(kinds, list):
        return list(DEFAULTS["auto_kinds"])
    out = [k for k in kinds if k in KIND_LABELS and k != "shortcut"]
    return out


def in_scope(filename, cfg):
    """这个文件是否属于老师希望自动关注的范围。"""
    return file_kind(filename) in auto_kinds(cfg)


def remember_ext_subject(cfg, filename, subject):
    """记住「这种扩展名的文件以后都放这里」。"""
    ext = file_ext(filename)
    if not ext or not subject:
        return False
    mapping = cfg.get("ext_subjects")
    if not isinstance(mapping, dict):
        mapping = {}
    mapping[ext] = subject
    cfg["ext_subjects"] = mapping
    return True


def ext_subject_for(filename, cfg):
    mapping = cfg.get("ext_subjects")
    if not isinstance(mapping, dict):
        return ""
    return str(mapping.get(file_ext(filename), "") or "")


# --------------------------------------------------------------- 建议算法
def _tokens(name):
    """把文件名切成可用于相似度比较的片段。"""
    base = os.path.splitext(name)[0].lower()
    parts = re.split(r"[\s_\-—()（）\[\]【】.,，。;；:：+&@#]+", base)
    out = []
    for p in parts:
        if not p:
            continue
        out.append(p)
        # 中文再按 2 字滑窗切
        for i in range(len(p) - 1):
            out.append(p[i:i + 2])
    return set(x for x in out if x)


def load_history():
    p = paths.history_path()
    if not os.path.isfile(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def append_history(name, subject, limit=300):
    with _LOCK:
        hist = load_history()
        hist.append({"name": name, "subject": subject})
        if len(hist) > limit:
            hist = hist[-limit:]
        try:
            with open(paths.history_path(), "w", encoding="utf-8") as f:
                json.dump(hist, f, ensure_ascii=False, indent=1)
        except Exception:
            pass


def keyword_hit(filename, cfg):
    """只按科目关键词匹配，返回 (科目名, 得分)。"""
    lower = filename.lower()
    best = ("", 0)
    for s in cfg.get("subjects", []):
        sname = s.get("name", "")
        if not sname:
            continue
        for kw in s.get("keywords", []):
            k = str(kw).strip()
            if not k:
                continue
            if k.lower() in lower:
                score = 60 + 12 * len(k)
                if score > best[1]:
                    best = (sname, score)
    return best


def suggest_subject(filename, cfg, history=None):
    """返回 (科目名 or '', 理由)。"""
    names = subject_names(cfg)
    if not names:
        return "", ""
    lower = filename.lower()
    best = ("", 0, "")

    # 1) 历史记录：老师以前把类似名字的文件放进了哪个科目
    hist = history if history is not None else load_history()
    ftoks = _tokens(filename)
    if ftoks:
        for rec in reversed(hist[-250:]):
            rn = rec.get("name", "")
            sub = rec.get("subject", "")
            if sub not in names:
                continue
            rtoks = _tokens(rn)
            if not rtoks:
                continue
            inter = ftoks & rtoks
            if not inter:
                continue
            score = 40 + 6 * len(inter)
            if rn.lower() == lower:
                score += 120
            if score > best[1]:
                best = (sub, score, "与历史记录「%s」相似" % rn)

    # 2) 科目关键词命中
    for s in cfg.get("subjects", []):
        sname = s.get("name", "")
        if not sname or sname not in names:
            continue
        for kw in s.get("keywords", []):
            k = str(kw).strip()
            if not k:
                continue
            if k.lower() in lower:
                score = 60 + 12 * len(k)
                if score > best[1]:
                    best = (sname, score, "文件名包含「%s」" % k)

    # 3) 老师亲自指定过的扩展名映射（比"按类型兜底"可信，但弱于文件名关键词）
    ext = os.path.splitext(filename)[1].lower()
    chosen = ext_subject_for(filename, cfg)
    if chosen and chosen in names and 58 > best[1]:
        best = (chosen, 58, "您之前指定过「%s」放这里" % ext)

    # 4) 扩展名兜底
    if ext in EXT_SUBJECT:
        cand = EXT_SUBJECT[ext]
        for s in cfg.get("subjects", []):
            if s.get("name") == cand and 30 > best[1]:
                best = (cand, 30, "按文件类型推测")
            # 名称里带"视频"的文件夹
            if "视频" in s.get("name", "") and ext in (".mp4", ".avi", ".mkv", ".mov", ".wmv") \
                    and 30 > best[1]:
                best = (s["name"], 30, "按文件类型推测")

    return best[0], best[2]


# ------------------------------------------------------------ 辅助
def human_size(n):
    try:
        n = float(n)
    except Exception:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return "%d B" % int(n)
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return ""


def short_name(name, limit=42):
    if len(name) <= limit:
        return name
    keep = limit - 1
    head = int(keep * 0.6)
    return name[:head] + "…" + name[-(keep - head):]
