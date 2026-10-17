# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""可视化检查：按场景起 App、显示对应界面，供截图核对。

用法::  python visual_check.py <scene>       # bubble | main | settings | move
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dsr import config, winapi  # noqa: E402

FAKE = os.path.join(tempfile.gettempdir(), "dsr_fake_desktop")


def main():
    scene = (sys.argv[1] if len(sys.argv) > 1 else "bubble").lower()
    winapi.set_dpi_awareness()
    shutil.rmtree(FAKE, ignore_errors=True)
    os.makedirs(os.path.join(FAKE, "数学"), exist_ok=True)
    os.makedirs(os.path.join(FAKE, "英语"), exist_ok=True)

    cfg = config.load()
    cfg.update({
        "desktop_path": FAKE,
        "first_run": False,
        "autostart": False,
        "sound": False,
        "watch_interval": 0.5,
        "duration": 60,
        "corner": "br",
        "character": os.environ.get("DSR_CHAR") or "teacher_f",
    })
    # 用固定的科目集合，保证测试可复现（不受真实桌面影响）
    cfg["subjects"] = [config.normalize_subject(n)
                       for n in ("数学", "英语", "语文")]

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    from dsr.app import App
    app = App(root, cfg)
    app._char_rot = int(os.environ.get("DSR_CHAR_ROT", "0"))
    app.start()

    if scene == "bubble":
        def make():
            with open(os.path.join(FAKE, "第三单元数学测试卷.docx"), "wb") as f:
                f.write(b"x" * 2048)
        root.after(1500, make)
    elif scene == "bubble2":
        # 连弹两个气泡，用来核对「同一形象多张立绘轮换」
        def make_a():
            with open(os.path.join(FAKE, "第三单元数学测试卷.docx"), "wb") as f:
                f.write(b"x" * 2048)
        def make_b():
            with open(os.path.join(FAKE, "英语听力练习.mp3"), "wb") as f:
                f.write(b"x" * 2048)
        root.after(1500, make_a)
        root.after(3200, make_b)
    elif scene == "move":
        def make():
            with open(os.path.join(FAKE, "英语听力练习.mp3"), "wb") as f:
                f.write(b"x" * 40000)
        root.after(1500, make)
        # 自动点"移动"按钮，验证真正归档
        def click():
            wins = list(__import__("dsr.bubble", fromlist=["x"])._windows.values())
            if wins:
                wins[0].fire("move")
        root.after(4000, click)
    elif scene == "ask":
        # 认不出科目的图片 -> 应该弹出"询问放哪儿"的气泡
        def make():
            with open(os.path.join(FAKE, "IMG_20261010.jpg"), "wb") as f:
                f.write(b"x" * 4096)
        root.after(1500, make)
    elif scene == "pick":
        def make2():
            p = os.path.join(FAKE, "扫描件_期末.jpg")
            with open(p, "wb") as f:
                f.write(b"x" * 4096)
            root.after(2500, lambda: app.open_picker(p, 4096, "桌面", "image"))
        root.after(1500, make2)
    elif scene == "other":
        # 认得出科目 -> 气泡第二枚按钮「放置在其他文件夹」应打开选择窗口
        def make3():
            with open(os.path.join(FAKE, "第三单元数学测试卷.docx"), "wb") as f:
                f.write(b"x" * 4096)
        def click_other():
            import dsr.bubble as _b
            wins = list(_b._windows.values())
            if wins:
                wins[0].fire("other")
                print("fired other on hwnd=%s" % wins[0].hwnd, flush=True)
            else:
                print("no bubble window", flush=True)
        root.after(1500, make3)
        root.after(4200, click_other)
    elif scene == "main":
        root.after(800, app.open_main)
    elif scene == "settings":
        root.after(800, app.open_settings)
    elif scene == "settings_scroll":
        def go_scroll():
            app.open_settings()
            root.after(600, lambda: app.settings_window.win.geometry("620x720+40+10"))
        root.after(800, go_scroll)
    elif scene == "settings_char":
        # 滚到「提示人物」卡片，验收人物缩略图
        def go_char():
            app.open_settings()
            root.after(900, lambda: app.settings_window.scroll.canvas.yview_moveto(0.42))
        root.after(800, go_char)
    elif scene == "both":
        root.after(800, app.open_main)
        root.after(1400, app.open_settings)

    shot_dir = os.environ.get("DSR_SHOT")
    if shot_dir and scene in ("main", "settings", "both", "pick", "other",
                              "settings_scroll", "settings_char"):
        def shoot():
            import win_shot
            os.makedirs(shot_dir, exist_ok=True)
            from dsr import paths as _p
            targets = {"main": _p.APP_NAME,
                       "settings": "设置 - %s" % _p.APP_NAME,
                       "pick": "选择归档文件夹"}
            for key, title in targets.items():
                h = win_shot.find(title)
                if h:
                    p = win_shot.grab(h, os.path.join(shot_dir, key + ".png"))
                    print("shot %s hwnd=%s -> %s" % (key, h, p), flush=True)
                else:
                    print("shot %s: window not found" % key, flush=True)
            # 选择窗口标题里带文件名，用前缀匹配兜底
            if scene in ("pick", "other"):
                h = win_shot.find(None, prefix="选择归档文件夹")
                if h:
                    p = win_shot.grab(h, os.path.join(shot_dir, "pick.png"))
                    print("shot pick(prefix) -> %s" % p, flush=True)
        root.after(int(os.environ.get("DSR_SHOT_AT", "3000")), shoot)

    root.after(int(os.environ.get("DSR_LIFE", "14000")), app.shutdown)

    # 把气泡窗口"实际上屏"的那张位图存下来（无头环境下代替截图核对）
    dump_dir = os.environ.get("DSR_DUMP")
    if dump_dir:
        def dump():
            from dsr import bubble as bmod
            os.makedirs(dump_dir, exist_ok=True)
            for i, w in enumerate(list(bmod._windows.values())):
                img = getattr(w, "_last_img", None)
                try:
                    import ctypes
                    rc = winapi.RECT()
                    winapi.user32.GetWindowRect(w.hwnd, ctypes.byref(rc))
                    rect = (rc.left, rc.top, rc.right, rc.bottom)
                    vis = bool(winapi.user32.IsWindowVisible(w.hwnd))
                except Exception as e:  # noqa: BLE001
                    rect, vis = "err:%r" % (e,), "?"
                print("hwnd=%s rect=%s visible=%s size=%s" % (
                    w.hwnd, rect, vis, img.size if img is not None else None),
                    flush=True)
                if img is not None:
                    img.save(os.path.join(dump_dir, "%s_%d.png" % (scene, i)))
        root.after(int(os.environ.get("DSR_DUMP_AT", "4000")), dump)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
