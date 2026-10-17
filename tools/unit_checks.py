# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""功能性自检：托盘、开机自启动注册表、U 盘扫描、声音、单实例。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dsr import config, paths, usbscan, winapi  # noqa: E402

ok_all = True


def check(name, cond, extra=""):
    global ok_all
    ok_all = ok_all and bool(cond)
    print("%-4s %s %s" % ("PASS" if cond else "FAIL", name, extra), flush=True)


def main():
    winapi.set_dpi_awareness()
    print("python:", sys.version.split()[0], "frozen:", paths.is_frozen())

    # ---------------- 开机自启动 ----------------
    had = winapi.get_autostart_command()
    r1 = winapi.set_autostart(True)
    cur = winapi.get_autostart_command()
    check("开启开机自启动", r1[0] and cur, repr(cur))
    check("启动命令指向本程序", bool(cur) and ("main.py" in str(cur)
                                          or "科目" in str(cur)
                                          or "classDesktopManager" in str(cur)),
          repr(cur))
    r2 = winapi.set_autostart(False)
    check("关闭开机自启动", r2[0] and not winapi.get_autostart_command())
    if had:
        winapi.set_autostart(True)

    # ---------------- 单实例 ----------------
    # 用独立的互斥体名，免得被正在运行的正式实例影响
    mutex = "Local\\classDesktopManager.UnitCheck.%d" % os.getpid()
    a = winapi.acquire_single_instance(mutex)
    check("单实例互斥体首次获取", a, repr(a))
    b = winapi.acquire_single_instance(mutex)
    check("单实例互斥体第二次被拒", not b, repr(b))
    real = winapi.acquire_single_instance()
    print("   （说明）正式互斥体可用：%s（False 表示已有实例在运行）" % real)

    # ---------------- U 盘扫描 ----------------
    fake = os.path.join(tempfile.gettempdir(), "dsr_fake_usb")
    shutil.rmtree(fake, ignore_errors=True)
    os.makedirs(os.path.join(fake, "课件", "第三单元"), exist_ok=True)
    target = os.path.join(fake, "课件", "第三单元", "数学练习卷.docx")
    with open(target, "wb") as f:
        f.write(b"y" * 4096)
    real_roots = usbscan.removable_roots
    usbscan.removable_roots = lambda: [fake]
    try:
        usbscan.invalidate()
        got = usbscan.find_source("数学练习卷.docx", 4096)
        check("U 盘里找到同名文件", bool(got) and got[0] == fake, repr(got))
        usbscan.invalidate()
        got2 = usbscan.find_source("根本不存在的文件.docx", 123)
        check("U 盘里没有则返回空", not (got2 and got2[0]), repr(got2))
    finally:
        usbscan.removable_roots = real_roots
        usbscan.invalidate()
    check("可移动盘类型判定", winapi.drive_type("C:\\") != winapi.DRIVE_REMOVABLE,
          "C: type=%s" % winapi.drive_type("C:\\"))

    # ---------------- 科目识别 ----------------
    cfg = config.load()
    cfg["subjects"] = [config.normalize_subject(n) for n in ("数学", "英语")]
    for fn, want in (("第三单元数学测试卷.docx", "数学"),
                     ("英语听力练习.mp3", "英语"),
                     ("三年级语文上册.docx", None)):
        subj, reason = config.suggest_subject(fn, cfg)
        hit, score = config.keyword_hit(fn, cfg)
        check("识别 %s" % fn, (subj == want) if want else (hit is None or score < 60),
              "-> %s (%s) kw=%s/%s" % (subj, reason, hit, score))

    # ---------------- 声音 ----------------
    try:
        import winsound
        winsound.PlaySound("SystemAsterisk",
                           winsound.SND_ALIAS | winsound.SND_ASYNC)
        check("提示音可播放", True)
    except Exception as e:  # noqa: BLE001
        check("提示音可播放", False, repr(e))

    # ---------------- 桌面/资源 ----------------
    check("桌面路径", os.path.isdir(winapi.get_desktop_path()),
          winapi.get_desktop_path())
    for cid, name, p in paths.builtin_characters():
        check("人物素材 %s" % cid, os.path.isfile(p), os.path.basename(p))
    check("托盘图标文件", os.path.isfile(paths.asset_path("app.ico")))

    # ---------------- 多立绘轮换 ----------------
    variants = paths.character_files("teacher_nene")
    check("绫宁宁有两张立绘", len(variants) == 2,
          [os.path.basename(v) for v in variants])
    ids = [c[0] for c in paths.builtin_characters()]
    check("变体图不出现在人物列表里", "teacher_nene_2" not in ids, ids)

    from dsr.app import App

    class _Rot:
        _character_path = App._character_path

        def __init__(self):
            self.cfg = {"character": "teacher_nene"}
            self._char_rot = 0

    r = _Rot()
    seq = [os.path.basename(r._character_path()) for _ in range(4)]
    check("每次取图都在轮换", seq == ["teacher_nene.png", "teacher_nene_2.png",
                                      "teacher_nene.png", "teacher_nene_2.png"],
          seq)

    print("\n结果：", "全部通过" if ok_all else "有失败项")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
