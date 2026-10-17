# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""起一次打包好的 exe，造一个新文件，然后持续枚举气泡窗口的真实矩形。

不杀进程、不做断言，纯粹用于观察 exe 里气泡窗口的真实尺寸/位置，
配合 app.log 里的 DPI 诊断行定位「打包后缩放不对」的问题。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.wnd_enum import scan  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "src")
sys.path.insert(0, SRC)

from dsr import config, paths, winapi  # noqa: E402

winapi.set_dpi_awareness()

EXE = os.path.join(HERE, "dist", "classDesktopManager.exe")
DESK = os.path.join(os.environ["TEMP"], "dsr_probe_desktop")


def main():
    shutil.rmtree(DESK, ignore_errors=True)
    os.makedirs(os.path.join(DESK, "数学"), exist_ok=True)
    ad = paths.appdata_dir()
    os.makedirs(ad, exist_ok=True)
    for f in ("config.json", "history.json", "app.log"):
        p = os.path.join(ad, f)
        if os.path.isfile(p):
            os.remove(p)
    cfg = config.load()
    cfg.update({"desktop_path": DESK, "first_run": False, "autostart": False,
                "sound": False, "start_minimized": True, "detect_mode": "all",
                "watch_interval": 0.5, "duration": 60, "paused": False})
    cfg["subjects"] = [config.normalize_subject(n) for n in ("数学", "英语")]
    config.save(cfg)

    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    print("exe pid=%s" % proc.pid, flush=True)
    deadline = time.time() + 45
    while time.time() < deadline and not os.path.isfile(paths.log_path()):
        time.sleep(0.5)
    time.sleep(2.5)
    with open(os.path.join(DESK, "第三单元数学测试卷.docx"), "wb") as f:
        f.write(b"x" * 8000)
    time.sleep(3.0)
    for _ in range(6):
        rows = scan()
        print("--- %s 共 %d 个窗口" % (time.strftime("%H:%M:%S"), len(rows)),
              flush=True)
        for cls, hwnd, pid, name, rect, vis in rows:
            print("  %-14s hwnd=%-8s pid=%-6s %-30s rect=%s vis=%s"
                  % (cls, hwnd, pid, name, rect, vis), flush=True)
        time.sleep(1.5)
    log = open(paths.log_path(), encoding="utf-8", errors="replace").read()
    print("---- app.log ----", flush=True)
    print(log, flush=True)
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
