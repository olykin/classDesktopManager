# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""端到端冒烟测试：起 App -> 造一个"新文件" -> 看气泡是否弹出 -> 退出。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dsr import config, paths, winapi  # noqa: E402

FAKE_DESKTOP = os.path.join(tempfile.gettempdir(), "dsr_fake_desktop")


def main():
    winapi.set_dpi_awareness()
    shutil.rmtree(FAKE_DESKTOP, ignore_errors=True)
    os.makedirs(os.path.join(FAKE_DESKTOP, "数学"), exist_ok=True)

    cfg = config.load()
    cfg["desktop_path"] = FAKE_DESKTOP
    cfg["first_run"] = False
    cfg["autostart"] = False
    cfg["sound"] = False
    cfg["watch_interval"] = 0.5
    cfg["duration"] = 12

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    from dsr.app import App
    app = App(root, cfg)
    app.start()
    print("[t] app started", flush=True)

    def make_file():
        p = os.path.join(FAKE_DESKTOP, "第三单元数学测试卷.docx")
        with open(p, "wb") as f:
            f.write(b"x" * 2048)
        print("[t] created", p, flush=True)

    def report():
        print("[t] bubbles =", app.bubbles.count() if app.bubbles else "n/a",
              flush=True)

    root.after(1200, make_file)
    root.after(3200, report)
    root.after(5000, report)

    def later():
        print("[t] open main window", flush=True)
        app.open_main()

    root.after(4200, later)

    def quit_soon():
        print("[t] shutting down", flush=True)
        app.shutdown()

    root.after(9000, quit_soon)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    print("[t] done", flush=True)


if __name__ == "__main__":
    main()
