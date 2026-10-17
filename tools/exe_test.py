# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""对打包出来的 exe 做一次真机端到端验证（不依赖屏幕是否解锁）。"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dsr import config, paths  # noqa: E402

EXE = os.path.join(ROOT, "dist", "classDesktopManager.exe")
DESK = os.path.join(tempfile.gettempdir(), "dsr_exe_desktop")
ok = True


def check(name, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print("%-4s %s %s" % ("PASS" if cond else "FAIL", name, extra), flush=True)


def kill_prev():
    """只杀本仓库 dist 下的实例，绝不碰老师自己那份（可能在别处运行）。"""
    dist = os.path.dirname(EXE).lower()
    ps = ("Get-Process | Where-Object { $_.Path -and "
          "$_.Path.ToLower().StartsWith('%s') } | "
          "ForEach-Object { taskkill /F /T /PID $_.Id }" % dist.replace("'", "''"))
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   capture_output=True)
    time.sleep(1.0)


def _proc_path(pid):
    """取进程的映像全路径（用于确认窗口属于我们 dist 下的那份 exe）。"""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x1000, False, pid)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        n = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return buf.value
        return ""
    finally:
        k32.CloseHandle(h)


def find_win(cls, pid=0):
    """找类名为 cls 的顶层窗口。

    onefile 模式下 Popen 拿到的是**引导进程**，真正的 App 跑在它的子进程里，
    所以不能按 pid 过滤；改为只认「映像路径 == 本仓库 dist 下那份 exe」的窗口，
    这样绝不会误命中老师自己那份实例。
    """
    import ctypes
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    want = os.path.abspath(EXE).lower()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _l):
        buf = ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(hwnd, buf, 256)
        if buf.value == cls:
            p = wintypes.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if os.path.abspath(_proc_path(int(p.value))).lower() == want:
                found.append(hwnd)
                return False
        return True

    u32.EnumWindows(cb, 0)
    return found[0] if found else 0



def main():
    kill_prev()
    if not os.path.isfile(EXE):
        print("exe 不存在：%s" % EXE, flush=True)
        return 1
    print("exe: %s (%.1f MB)" % (EXE, os.path.getsize(EXE) / 1048576.0), flush=True)

    shutil.rmtree(DESK, ignore_errors=True)
    os.makedirs(os.path.join(DESK, "数学"), exist_ok=True)

    # 清空配置/日志，准备一份指向临时桌面的配置
    ad = paths.appdata_dir()
    os.makedirs(ad, exist_ok=True)
    for f in ("config.json", "history.json", "app.log"):
        p = os.path.join(ad, f)
        if os.path.isfile(p):
            os.remove(p)
    cfg = config.load()
    cfg.update({"desktop_path": DESK, "first_run": False, "autostart": False,
                "sound": False, "start_minimized": True, "detect_mode": "all",
                "watch_interval": 0.5, "duration": 25, "paused": False})
    cfg["subjects"] = [config.normalize_subject(n) for n in ("数学", "英语")]
    config.save(cfg)

    env = dict(os.environ)
    env["DSR_INSTANCE_SUFFIX"] = "exetest%d" % os.getpid()
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE), env=env)
    # onefile 首次启动要把内容解包到 %TEMP%\_MEIxxxx，机械盘 + 杀软下可能很慢
    deadline = time.time() + 45
    while time.time() < deadline:
        if os.path.isfile(paths.log_path()):
            break
        time.sleep(0.5)
    time.sleep(2.0)
    check("exe 进程存活（未崩溃）", proc.poll() is None, "poll=%s" % proc.poll())

    import ctypes
    u32 = ctypes.windll.user32
    tray_hwnd = find_win("DsrTrayWnd", proc.pid)
    check("托盘窗口已创建", bool(tray_hwnd), "hwnd=%s" % tray_hwnd)

    # 造一个"从 U 盘拷过来"的新文件
    target = os.path.join(DESK, "第三单元数学测试卷.docx")
    with open(target, "wb") as f:
        f.write(b"x" * 8000)
    deadline = time.time() + 30
    log = ""
    while time.time() < deadline:
        lp = paths.log_path()
        if os.path.isfile(lp):
            log = open(lp, encoding="utf-8", errors="replace").read()
            if "提醒：" in log:
                break
        time.sleep(1.0)
    check("exe 写入了启动日志", "启动" in log, repr(log[:120]))
    check("exe 弹出了提醒气泡", "提醒：" in log,
          repr([l for l in log.splitlines() if "提醒" in l][-1:]))
    check("文件仍在桌面（未自动移动）", os.path.isfile(target))
    bubble_hwnd = find_win("DsrBubbleWnd", proc.pid)
    check("气泡窗口已创建", bool(bubble_hwnd), "hwnd=%s" % bubble_hwnd)

    # ---- 真实点击「移动到「数学」」按钮（复现用户报的"按钮点不动"）----
    # 1) 在测试进程里按 app._show_file_bubble 的同样规则重建布局，拿到按钮矩形
    from dsr import bubbledraw, winapi
    # 本测试进程也必须声明 DPI 感知：否则 GetWindowRect / 工作区都会被系统
    # 按缩放比虚拟化（4K@250% 下会整体缩小 2.5 倍），量与 exe 真实窗口对不上
    winapi.set_dpi_awareness()
    print("测试进程 %s" % winapi.dpi_debug(), flush=True)
    name = os.path.basename(target)
    size = os.path.getsize(target)
    body = ["《%s》" % config.short_name(name, 34),
            "大小 %s · 来自 桌面" % config.human_size(size), ""]
    spec = {
        "title": "老师好呀，发现一个新文件",
        "body": body,
        "hint": "建议归档到「数学」文件夹 · 文件名包含「数学」",
        "buttons": [{"id": "move", "text": "移动到「数学」", "kind": "primary"},
                    {"id": "other", "text": "放置在其他文件夹", "kind": "ghost"},
                    {"id": "dismiss", "text": "稍后处理", "kind": "ghost"}],
        "accent": "#2F855A",
        "character_path": paths.builtin_characters()[0][2],
        "flip": False,
    }
    scale = winapi.dpi_scale_for_point()
    bub = [c for c in paths.builtin_characters() if c[0] == "teacher_f"]
    if bub:
        spec["character_path"] = bub[0][2]
    lay = bubbledraw.build_layout(spec, scale)
    bubbledraw.render(lay)   # 兼容旧版：按钮矩形以前只在 render 里生成

    rc = ctypes.wintypes.RECT()
    u32.GetWindowRect(ctypes.wintypes.HWND(bubble_hwnd), ctypes.byref(rc))
    wsize = (rc.right - rc.left, rc.bottom - rc.top)
    check("气泡尺寸与布局一致", wsize == (lay.width, lay.height),
          "窗口=%s 布局=%s" % (wsize, (lay.width, lay.height)))

    move_rect = [b for b in lay.buttons if b[4] == "move"]
    if not move_rect:
        check("找到「移动」按钮", False)
    else:
        mx0, my0, mx1, my1 = move_rect[0][:4]
        cx, cy = int((mx0 + mx1) / 2), int((my0 + my1) / 2)
        sx, sy = rc.left + cx, rc.top + cy
        from dsr import winapi as _w
        lp_scr = ((sy & 0xFFFF) << 16) | (sx & 0xFFFF)
        ht = u32.SendMessageW(ctypes.wintypes.HWND(bubble_hwnd),
                              _w.WM_NCHITTEST, 0, lp_scr)
        check("按钮中心命中气泡窗口(HTCLIENT)", ht == _w.HTCLIENT, "ht=%s" % ht)

        lp_cli = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF)
        u32.SendMessageW(ctypes.wintypes.HWND(bubble_hwnd), _w.WM_MOUSEMOVE, 0, lp_cli)
        time.sleep(0.1)
        u32.SendMessageW(ctypes.wintypes.HWND(bubble_hwnd), _w.WM_LBUTTONDOWN, 1, lp_cli)
        time.sleep(0.1)
        u32.SendMessageW(ctypes.wintypes.HWND(bubble_hwnd), _w.WM_LBUTTONUP, 0, lp_cli)

        moved = os.path.join(DESK, "数学", name)
        deadline = time.time() + 15
        while time.time() < deadline and not os.path.isfile(moved):
            time.sleep(0.5)
        check("点击后文件被归档到 数学\\", os.path.isfile(moved), moved)
        time.sleep(1.0)
        lp2 = paths.log_path()
        log2 = open(lp2, encoding="utf-8", errors="replace").read() \
            if os.path.isfile(lp2) else ""
        check("日志记录了归档", ("已移动" in log2) or ("归档" in log2),
              repr([l for l in log2.splitlines() if "移动" in l or "归档" in l][-1:]))
        log = log2

    # ---- v1.2.0：快捷方式不打扰 + 认不出科目时主动询问 ----
    with open(os.path.join(DESK, "某网站.url"), "wb") as f:
        f.write(b"x" * 128)
    with open(os.path.join(DESK, "IMG_20261010.jpg"), "wb") as f:
        f.write(b"x" * 4096)
    deadline = time.time() + 30
    while time.time() < deadline:
        log = open(paths.log_path(), encoding="utf-8", errors="replace").read() \
            if os.path.isfile(paths.log_path()) else ""
        if "询问：" in log:
            break
        time.sleep(1.0)
    check("认不出科目的图片会主动询问", "询问：" in log,
          repr([l for l in log.splitlines() if "询问" in l][-1:]))
    check("快捷方式不打扰", "某网站.url" not in log,
          repr([l for l in log.splitlines() if "url" in l][-1:]))
    check("询问时文件仍留在桌面",
          os.path.isfile(os.path.join(DESK, "IMG_20261010.jpg")))

    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   capture_output=True)
    try:
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    time.sleep(1.0)
    check("exe 已退出", proc.poll() is not None)
    print("\n---- app.log ----\n%s" % log, flush=True)
    print("结果：", "全部通过" if ok else "有失败项", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
