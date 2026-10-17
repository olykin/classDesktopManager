# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""生成 README 用的功能截图（docs/screenshots/*.png）。

用隔离的 APPDATA 与临时「桌面」，按 96 DPI 渲染，避免污染老师的真实配置；
tkinter 窗口从屏幕真实像素裁剪，气泡直接导出分层窗口的上屏位图（带透明通道）。

用法::

    python tools\\shoot_docs.py            # 输出到 docs\\screenshots
    python tools\\shoot_docs.py 输出目录
"""
from __future__ import annotations

import ctypes
import os
import shutil
import sys
import tempfile
import time
import tkinter as tk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

# 隔离配置目录（必须在 import dsr.paths 之前设置）
APP_TMP = os.path.join(tempfile.gettempdir(), "dsr_docs_appdata")
shutil.rmtree(APP_TMP, ignore_errors=True)
os.makedirs(APP_TMP, exist_ok=True)
os.environ["APPDATA"] = APP_TMP

from PIL import Image, ImageDraw, ImageGrab  # noqa: E402

from dsr import config, winapi  # noqa: E402

# 截图统一按 96 DPI 出图：窗口尺寸固定、在 1080p 上也能完整放下
_orig_scale = winapi.dpi_scale
winapi.dpi_scale = lambda: 1.0

FAKE = os.path.join(tempfile.gettempdir(), "dsr_docs_desktop")
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1
                      else os.path.join(ROOT, "docs", "screenshots"))

CTX = {
    "root": None,
    "app": None,
    "grabbed": {},
    "done": False,
}


# --------------------------------------------------------------- 小工具
def wait_ui(root, ms=350):
    """让 Tk 处理一轮事件后等待画面稳定。"""
    root.update()
    time.sleep(ms / 1000.0)
    root.update()


def decorate(img, pad=10):
    """给窗口截图加白边、圆角和 1px 描边（盖掉 Windows 圆角外的杂色）。"""
    w, h = img.size
    r = 9
    canvas = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (255, 255, 255, 255))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1],
                                           radius=r, fill=255)
    canvas.paste(img.convert("RGBA"), (pad, pad), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(
        [pad - 1, pad - 1, pad + w, pad + h], radius=r + 1,
        outline=(214, 222, 232, 255), width=1)
    return canvas.convert("RGB")


def grab_window(win, name):
    """按窗口可见区域从屏幕裁剪（标题栏 + 客户区），保存成 PNG。

    不用 GetWindowRect：Win10/11 的外框含一圈 8px 看不见的缩放边框，会把
    后面的桌面（或别的窗口）一起裁进来；改由客户区尺寸 + 标题栏高度拼出
    真正的可见矩形。
    """
    win.deiconify()
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass
    wait_ui(CTX["root"], 450)
    frame = int(win.wm_frame(), 16)
    rc = winapi.RECT()
    winapi.user32.GetWindowRect(frame, ctypes.byref(rc))
    cr = winapi.RECT()
    winapi.user32.GetClientRect(frame, ctypes.byref(cr))

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    pt = POINT(0, 0)
    winapi.user32.ClientToScreen(frame, ctypes.byref(pt))
    bbox = (pt.x, rc.top, pt.x + cr.right, pt.y + cr.bottom)
    img = ImageGrab.grab(bbox=bbox, all_screens=True).convert("RGB")
    # 上/右边缘有 1-2px 的 DWM 阴影缝，会漏出后面的桌面，先裁掉
    img = img.crop((2, 2, img.width - 2, img.height - 2))
    img = decorate(img)
    path = os.path.join(OUT, name + ".png")
    img.save(path)
    CTX["grabbed"][name] = path
    print("shot %-22s %s -> %s" % (name, bbox, path), flush=True)
    return path


def grab_bubble(name, tries=14):
    """导出气泡分层窗口实际上屏的位图（RGBA，保留透明）。"""
    from dsr import bubble as bmod
    wins = [w for w in list(bmod._windows.values())
            if getattr(w, "_last_img", None) is not None]
    if not wins and tries > 0:
        CTX["root"].after(300, lambda: grab_bubble(name, tries - 1))
        return None
    if not wins:
        print("shot %-22s bubble not found" % name, flush=True)
        return None
    img = wins[-1]._last_img
    path = os.path.join(OUT, name + ".png")
    img.save(path)
    CTX["grabbed"][name] = path
    print("shot %-22s %s -> %s" % (name, img.size, path), flush=True)
    return wins[-1]


def close_bubbles():
    from dsr import bubble as bmod
    for w in list(bmod._windows.values()):
        try:
            w.begin_close()
        except Exception:
            pass


def make_scan_image(path):
    """造一张像扫描件的图片，让选择窗口有缩略图可看。"""
    from PIL import ImageDraw, ImageFont
    w, h = 520, 700
    img = Image.new("RGB", (w, h), (252, 250, 244))
    d = ImageDraw.Draw(img)
    d.rectangle([18, 18, w - 18, h - 18], outline=(226, 220, 206), width=2)
    try:
        f_big = ImageFont.truetype("msyh.ttc", 34)
        f = ImageFont.truetype("msyh.ttc", 20)
    except Exception:
        f_big = f = None
    d.text((44, 48), "期末复习提纲", fill=(40, 48, 60), font=f_big)
    d.text((44, 104), "语文 · 第三单元", fill=(110, 118, 130), font=f)
    for i in range(15):
        y = 156 + i * 32
        d.line([44, y, w - 44, y], fill=(214, 216, 220), width=1)
    img.save(path, quality=92)


# --------------------------------------------------------------- 场景
def build_env():
    shutil.rmtree(FAKE, ignore_errors=True)
    for name in ("数学", "英语", "语文"):
        os.makedirs(os.path.join(FAKE, name), exist_ok=True)

    cfg = config.load()
    cfg.update({
        "desktop_path": FAKE,
        "first_run": False,
        "autostart": False,
        "sound": False,
        "watch_interval": 0.5,
        "duration": 90,
        "corner": "br",
        "character": "teacher_nene",
        "detect_mode": "smart",
    })
    cfg["subjects"] = [config.normalize_subject(n)
                       for n in ("数学", "英语", "语文")]

    # 预置归档历史，主界面「最近的归档记录」才有内容
    hist = [
        ("第一单元数学随堂练习.docx", "数学"),
        ("英语听力练习.mp3", "英语"),
        ("语文期末复习提纲.pdf", "语文"),
        ("口算天天练.xlsx", "数学"),
    ]
    import json
    with open(os.path.join(APP_TMP, "classDesktopManager", "history.json"),
              "w", encoding="utf-8") as f:
        json.dump([{"name": n, "subject": s} for n, s in hist],
                  f, ensure_ascii=False, indent=1)
    return cfg


def run():
    os.makedirs(OUT, exist_ok=True)
    winapi.set_dpi_awareness()
    cfg = build_env()

    root = tk.Tk()
    root.withdraw()
    root.tk.call("tk", "scaling", 96.0 / 72.0)   # 强制 96 DPI 的字号基准
    CTX["root"] = root

    from dsr.app import App
    app = App(root, cfg)
    CTX["app"] = app
    app.start()

    def at(ms, fn):
        root.after(ms, fn)

    # 1) 主界面 ---------------------------------------------------------
    def open_main():
        app.open_main()
        # 与默认窗口尺寸一致，位置挪到左上干净区
        app.main_window.win.geometry("560x680+120+40")

    at(700, open_main)
    at(1900, lambda: grab_window(app.main_window.win, "01-main"))
    at(2900, lambda: app.main_window.hide())

    # 2) 设置界面（两屏：常规 + 提示人物）-------------------------------
    def open_settings():
        app.open_settings()
        app.settings_window.win.geometry("620x720+120+30")

    at(3300, open_settings)

    def scroll_char():
        # 把「关注哪些文件」卡片滚到顶部：整卡 + 下方「提示人物」都能入镜
        try:
            sf = app.settings_window.scroll
            body = sf.body
            body.update_idletasks()
            cards = [w for w in body.winfo_children() if w.winfo_height() > 80]
            target = cards[3]
            total = sf.canvas.bbox("all")[3] or 1
            sf.canvas.yview_moveto(max(0.0, target.winfo_y() / float(total)))
        except Exception as e:  # noqa: BLE001
            print("scroll failed: %r" % (e,))

    at(4400, lambda: grab_window(app.settings_window.win, "05-settings"))
    at(5500, scroll_char)
    at(6500, lambda: grab_window(app.settings_window.win, "06-settings-character"))
    at(7500, lambda: app.settings_window.hide())

    # 3) 认得出的文件 -> 建议归档气泡 ------------------------------------
    def make_docx():
        p = os.path.join(FAKE, "第三单元数学测试卷.docx")
        with open(p, "wb") as f:
            f.write(b"x" * 184320)

    at(7700, make_docx)
    at(10000, lambda: grab_bubble("02-bubble"))

    # 4) 一键归档成功气泡 ------------------------------------------------
    def click_move():
        from dsr import bubble as bmod
        wins = [w for w in list(bmod._windows.values())
                if getattr(w, "_last_img", None) is not None]
        if wins:
            wins[-1].fire("move")

    at(10800, click_move)
    at(12800, lambda: grab_bubble("03-done"))

    # 5) 认不出科目 -> 询问气泡 ------------------------------------------
    def make_unknown():
        close_bubbles()
        p = os.path.join(FAKE, "IMG_20261010.jpg")
        with open(p, "wb") as f:
            f.write(b"x" * 40960)

    at(13600, make_unknown)
    at(16500, lambda: grab_bubble("04-bubble-ask"))

    # 6) 「选择归档文件夹」窗口 ------------------------------------------
    def open_pick():
        close_bubbles()
        p = os.path.join(FAKE, "扫描件_期末.jpg")
        make_scan_image(p)
        app.open_picker(p, os.path.getsize(p), "桌面", "image")
        app.picker_window.win.geometry("580x620+220+70")

    at(17300, open_pick)
    at(19300, lambda: grab_window(app.picker_window.win, "07-picker"))

    def finish():
        if CTX["done"]:
            return
        CTX["done"] = True
        print("done: %s" % ", ".join(sorted(CTX["grabbed"])), flush=True)
        app.shutdown()

    at(21000, finish)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
