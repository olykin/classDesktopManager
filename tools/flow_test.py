# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""流程测试：识别 -> 气泡 -> 设置保存 -> 立即检测。"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dsr import config, paths, winapi  # noqa: E402

FAKE = os.path.join(tempfile.gettempdir(), "dsr_flow_desktop")
ok = True


def check(name, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("%-4s %s %s" % ("PASS" if cond else "FAIL", name, extra), flush=True)


def main():
    winapi.set_dpi_awareness()
    shutil.rmtree(FAKE, ignore_errors=True)
    os.makedirs(os.path.join(FAKE, "数学"), exist_ok=True)
    os.makedirs(os.path.join(FAKE, "英语"), exist_ok=True)

    cfg = config.load()
    cfg.update({"desktop_path": FAKE, "first_run": False, "autostart": False,
                "sound": False, "watch_interval": 0.4, "duration": 20,
                "paused": False, "character": "teacher_m", "corner": "bl"})
    cfg["subjects"] = [config.normalize_subject(n) for n in ("数学", "英语")]

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    from dsr.app import App
    app = App(root, cfg)
    app.start()

    result = {}

    def step1():
        with open(os.path.join(FAKE, "数学第三单元测试卷.docx"), "wb") as f:
            f.write(b"z" * 5000)

    def step2():
        result["bubbles"] = app.bubbles.count()
        check("新文件触发气泡", app.bubbles.count() >= 1,
              "count=%s" % app.bubbles.count())
        app.open_settings()

    def step3():
        sw = app.settings_window
        check("设置窗口已创建", sw is not None and sw.alive())
        sw.v_corner.set("tr")
        sw.v_duration.set(23)
        sw.v_character.set("teacher_miku")
        sw.v_mode.set("all")
        sw.v_sound.set(True)
        sw.v_autostart.set(False)
        sw.save()
        saved = json.load(open(paths.config_path(), encoding="utf-8"))
        check("config.json 已写入", saved.get("corner") == "tr"
              and saved.get("duration") == 23
              and saved.get("character") == "teacher_miku"
              and saved.get("detect_mode") == "all", json.dumps(
                  {k: saved.get(k) for k in
                   ("corner", "duration", "character", "detect_mode")},
                  ensure_ascii=False))
        check("app.cfg 已同步", app.cfg.get("corner") == "tr"
              and app.cfg.get("duration") == 23)
        check("开机自启动保持关闭", not winapi.get_autostart_command())
        check("设置窗口已隐藏", not sw.win.winfo_ismapped())

    def step4():
        app.check_now()

    def step5():
        check("立即检测也能弹气泡", app.bubbles.count() >= 1,
              "count=%s" % app.bubbles.count())
        # 直接归档
        app._spawn(app._move_file, os.path.join(FAKE, "数学第三单元测试卷.docx"),
                   "数学", "桌面")

    def step6():
        moved = os.path.isfile(
            os.path.join(FAKE, "数学", "数学第三单元测试卷.docx"))
        check("一键归档成功", moved)
        hist = config.load_history()
        check("历史记录已写入", any(h.get("subject") == "数学" for h in hist),
              str(hist[-1:] if hist else []))

    def finish():
        app.shutdown()

    for delay, fn in ((1400, step1), (3200, step2), (4200, step3),
                      (5000, step4), (6200, step5), (7600, step6),
                      (8600, finish)):
        root.after(delay, fn)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

    print("\n结果：", "全部通过" if ok else "有失败项", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
