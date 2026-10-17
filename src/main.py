# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""classDesktopManager —— 程序入口。

用法::

    python main.py              启动并显示主界面
    python main.py --tray       启动后直接最小化到系统托盘（开机自启用）
    python main.py --settings   启动后直接打开设置界面
"""
from __future__ import annotations

import os
import sys
import time
import traceback

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    __package__ = "dsr"

from dsr import config, paths, winapi  # noqa: E402


def _boot_log(msg):
    """最早期、最不可能失败的日志：打包成无控制台的 exe 后靠它排错。"""
    try:
        d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"),
                         "classDesktopManager")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "app.log"), "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


def _die(msg, code=1):
    try:
        import tkinter.messagebox as mb
        import tkinter as tk
        r = tk.Tk()
        r.withdraw()
        mb.showerror(paths.APP_NAME, msg)
        r.destroy()
    except Exception:
        pass
    try:
        with open(paths.log_path(), "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass
    sys.exit(code)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    winapi.set_dpi_awareness()
    _boot_log("DPI %s" % winapi.dpi_debug())

    # --- 只允许一个实例（已有实例时静默退出，避免开机自启时弹窗打扰）
    if not winapi.acquire_single_instance():
        try:
            with open(paths.log_path(), "a", encoding="utf-8") as f:
                f.write("已有实例在运行，本次启动退出。\n")
        except Exception:
            pass
        return 0

    # --- 配置
    cfg = config.load()
    cfg["first_run"] = cfg.get("first_run", True)

    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    root.title(paths.APP_NAME)
    try:
        root.iconbitmap(paths.asset_path("app.ico"))
    except Exception:
        pass

    # 主界面本身作为根窗口显示
    root.protocol("WM_DELETE_WINDOW", lambda: app.main_window.on_close()
                  if app.main_window else app.shutdown())

    from dsr.app import App
    app = App(root, cfg)

    def on_error(exc, val, tb):
        try:
            from dsr.app import _log
            _log("未捕获异常：%s" % "".join(traceback.format_exception(exc, val, tb)))
        except Exception:
            pass

    sys.excepthook = on_error
    root.report_callback_exception = on_error

    app.start()

    # --- 首启动问候
    if cfg.get("first_run"):
        cfg["first_run"] = False
        config.save(cfg)
        root.after(1400, app.first_run_greeting)

    # --- 启动参数
    start_min = bool(cfg.get("start_minimized", True))
    if "--tray" in argv:
        start_min = True
    if "--settings" in argv:
        root.after(300, app.open_settings)
    elif not start_min:
        root.after(200, app.open_main)
    else:
        root.after(600, lambda: app._show({
            "title": "已在后台运行",
            "body": ["我会一直在右下角托盘里待命，",
                     "发现新文件就出来提醒您。"],
            "hint": "单击托盘图标可以打开主界面或退出",
            "accent": "#2B6CB0",
            "buttons": [{"id": "main", "text": "打开主界面", "kind": "primary"},
                        {"id": "dismiss", "text": "知道了", "kind": "ghost"}],
        }, duration=8, on_action=lambda aid, win: (
            win.begin_close(), app._ui(app.open_main))
            if aid == "main" else None))

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    _boot_log("==== 进程启动 frozen=%s argv=%s" % (
        getattr(sys, "frozen", False), sys.argv[1:]))
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:
        _boot_log("启动失败：\n" + traceback.format_exc())
        raise
