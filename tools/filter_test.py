# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""筛选与询问测试：快捷方式排除、类型过滤、认不出时询问并选择文件夹。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dsr import config, paths, winapi  # noqa: E402

FAKE = os.path.join(tempfile.gettempdir(), "dsr_filter_desktop")
ok = True


def check(name, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("%-4s %s %s" % ("PASS" if cond else "FAIL", name, extra), flush=True)


def write(name, size=4096):
    p = os.path.join(FAKE, name)
    with open(p, "wb") as f:
        f.write(b"x" * size)
    return p


def bubbles():
    from dsr import bubble as bmod
    return list(bmod._windows.values())


def main():
    winapi.set_dpi_awareness()
    shutil.rmtree(FAKE, ignore_errors=True)
    os.makedirs(os.path.join(FAKE, "数学"), exist_ok=True)
    os.makedirs(os.path.join(FAKE, "英语"), exist_ok=True)

    cfg = config.load()
    cfg.update({"desktop_path": FAKE, "first_run": False, "autostart": False,
                "sound": False, "watch_interval": 0.4, "duration": 30,
                "paused": False, "character": "teacher_f", "corner": "br",
                "detect_mode": "smart", "ask_unknown": True,
                "auto_kinds": ["office", "image"], "ext_subjects": {},
                "subjects": []})
    cfg["subjects"] = [config.normalize_subject(n) for n in ("数学", "英语")]

    # 清掉上一次跑测试留下的历史与"记住的类型"，保证可复现
    for p in (paths.history_path(), paths.config_path(), paths.log_path()):
        try:
            os.remove(p)
        except OSError:
            pass
    config.save(cfg)

    # ---------------------------------------------------------- 纯逻辑部分
    check("分类：docx -> 办公文档", config.file_kind("a.docx") == "office")
    check("分类：jpg -> 图片", config.file_kind("a.JPG") == "image")
    check("分类：lnk -> 快捷方式", config.file_kind("a.lnk") == "shortcut")
    check("分类：zip -> 压缩包", config.file_kind("a.zip") == "archive")
    check("快捷方式被排除", config.is_shortcut("数学.lnk")
          and config.is_shortcut("网址.URL"))
    check("关注范围内只有办公/图片",
          config.in_scope("a.docx", cfg) and config.in_scope("a.png", cfg)
          and not config.in_scope("a.zip", cfg)
          and not config.in_scope("a.mp3", cfg))

    from dsr.desktopwatch import _is_candidate
    check("监视器过滤快捷方式",
          not _is_candidate("数学作业.docx.lnk")
          and not _is_candidate("百度.url")
          and not _is_candidate("~$临时.docx")
          and _is_candidate("数学作业.docx"))

    check("认不出科目", config.suggest_subject("Scan_0001.pdf", cfg) == ("", ""))

    # ---------------------------------------------------------- 窗口流程
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()

    from dsr.app import App
    app = App(root, cfg)
    app.start()

    state = {}
    log_path = None

    def read_log():
        from dsr import paths
        try:
            with open(paths.log_path(), encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def step1():
        # 快捷方式 + 不在关注类型内的未知文件：都不该弹气泡
        write("数学练习.docx.lnk")
        write("某网站.url")
        write("资料包.zip")
        write("安装包.exe")

    def step2():
        check("快捷方式/无关类型不弹气泡", len(bubbles()) == 0,
              "bubbles=%d" % len(bubbles()))
        log = read_log()
        check("监视器没有上报快捷方式",
              "数学练习.docx.lnk" not in log and "某网站.url" not in log)
        check("日志记录了忽略无关类型",
              "不在关注类型内" in log or "忽略（无明确科目特征）" in log)
        # 第二道防线：即使直接喂给 App，快捷方式也要被丢掉
        app._handle_new_file(os.path.join(FAKE, "数学练习.docx.lnk"), 4096, 0)
        check("App 层二次拦截快捷方式", "忽略（快捷方式）" in read_log())
        # 认不出科目的图片 -> 应该弹"询问"气泡
        state["img"] = write("Scan_0001.pdf")

    def step3():
        bs = bubbles()
        check("认不出时弹出了询问气泡", len(bs) == 1, "bubbles=%d" % len(bs))
        if not bs:
            return
        spec_ids = [b[4] for b in bs[0].layout.buttons]
        check("询问气泡有「选择文件夹」按钮", "pick" in spec_ids, str(spec_ids))
        check("询问气泡没有「移动」按钮", "move" not in spec_ids)
        check("日志记录了询问", "询问：Scan_0001.pdf" in read_log())
        bs[0].fire("pick")

    def step4():
        pk = app.picker_window
        check("选择文件夹窗口已打开", pk is not None and pk.alive())
        if pk is None or not pk.alive():
            return
        names = list(pk._names)
        check("候选文件夹含桌面已有子文件夹",
              "数学" in names and "英语" in names, str(names))
        idx = list(pk._names).index("数学")
        pk.lst.selection_clear(0, "end")
        pk.lst.selection_set(idx)
        pk._on_select()
        pk.v_remember.set(True)
        pk._confirm()

    def step5():
        moved = os.path.isfile(os.path.join(FAKE, "数学", "Scan_0001.pdf"))
        check("选择后文件被移入「数学」", moved,
              str(sorted(os.listdir(FAKE))))
        check("记住了扩展名映射",
              app.cfg.get("ext_subjects", {}).get(".pdf") == "数学",
              str(app.cfg.get("ext_subjects")))
        check("选择窗口已隐藏",
              app.picker_window is None or not app.picker_window.win.winfo_ismapped())
        # 再放一个同类型文件：这次应该能直接认出科目
        state["img2"] = write("Scan_0002.pdf")

    def step6():
        sub, reason = config.suggest_subject("Scan_0002.pdf", app.cfg)
        check("同类文件已能自动识别", sub == "数学", "%s / %s" % (sub, reason))
        target = None
        for b in bubbles():
            ids = [x[4] for x in b.layout.buttons]
            body = " ".join(b.spec.get("body") or [])
            if "move" in ids and "Scan_0002.pdf" in body:
                target = b
        check("弹出了 Scan_0002 的「移动到」气泡", target is not None,
              "titles=%r" % [b.spec.get("title") for b in bubbles()])
        if target is not None:
            check("气泡带 move 按钮",
                  "move" in [x[4] for x in target.layout.buttons])
            target.fire("move")
        state["fired"] = target is not None

    def step7():
        check("同类文件被自动归档",
              os.path.isfile(os.path.join(FAKE, "数学", "Scan_0002.pdf")),
              str(sorted(os.listdir(FAKE))))

    def finish():
        app.shutdown()

    for delay, fn in ((1300, step1), (2600, step2), (5600, step3),
                      (6200, step4), (7400, step5), (9600, step6),
                      (11200, step7), (12000, finish)):
        root.after(delay, fn)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass

    print("\n结果：", "全部通过" if ok else "有失败项", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
