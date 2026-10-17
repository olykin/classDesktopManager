# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""应用控制器：把监视、识别、气泡提醒、托盘和 tkinter 界面串起来。

线程约定
--------
* 主线程            —— tkinter（Tk 只能住在主线程）
* ``UiThread``      —— Win32 消息线程，托盘图标与气泡窗口都归它
* ``DesktopWatcher``—— 轮询桌面目录
* 若干 worker       —— 文件移动、U 盘扫描等耗时操作
"""
from __future__ import annotations

import os
import queue
import shutil
import threading
import time
import traceback

from . import config, lesson, paths, usbscan, winapi
from .bubble import BubbleManager
from .desktopwatch import DesktopWatcher
from .tray import TrayIcon
from .uithread import UiThread

CORNERS = {"br": "右下角", "bl": "左下角", "tr": "右上角", "tl": "左上角"}


def _log(msg):
    try:
        line = "[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
        with open(paths.log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass


class App:
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        self.desktop = cfg.get("desktop_path") or winapi.get_desktop_path()
        cfg["desktop_path"] = self.desktop

        self.ui_thread = None
        self.tray = None
        self.bubbles = None
        self.watcher = None
        self.dl_watcher = None
        self.downloads = ""

        self.main_window = None
        self.settings_window = None
        self.picker_window = None

        self._ui_q = queue.Queue()
        self._detect_q = queue.Queue()
        self._workers = []
        self._closing = False
        self._last_alert = 0.0
        self._recent = {}          # path -> 提醒时间，避免重复打扰
        self._char_rot = 0         # 多立绘形象的轮换计数

    # =============================================================== 启动
    def start(self):
        _log("启动：桌面目录 = %s" % self.desktop)
        self._start_ui_thread()
        self._start_watcher()
        self._sync_downloads_watcher()
        self._start_detect_worker()
        self._sync_autostart()
        self.root.after(120, self._pump_ui)

    def _start_ui_thread(self):
        def setup(thread):
            tray = TrayIcon(paths.asset_path("app.ico"),
                            "classDesktopManager", on_command=self._on_tray_command)
            tray.create()
            tray.set_paused(bool(self.cfg.get("paused")))
            self.tray = tray
            self.bubbles = BubbleManager(scale=winapi.dpi_scale())
            return {"tray": tray, "bubbles": self.bubbles}

        def on_error(exc):
            _log("UI 线程异常：%r" % (exc,))
            _log(traceback.format_exc())

        self.ui_thread = UiThread(setup=setup, on_error=on_error)
        self.ui_thread.start()
        self.ui_thread.ready.wait(5.0)

    def _start_watcher(self):
        self.watcher = DesktopWatcher(
            self.desktop,
            interval=float(self.cfg.get("watch_interval") or 1.0),
            on_new_file=self._on_new_file,
            on_error=lambda e: _log("监视出错：%r" % (e,)))
        self.watcher.set_paused(bool(self.cfg.get("paused")))
        self.watcher.start()

    # ------------------------------------------------------- 下载文件夹
    def downloads_enabled(self):
        return bool(self.cfg.get("watch_downloads"))

    def resolve_downloads_path(self):
        """定位下载目录。

        设置里手动指定了目录就优先用它；否则交给 Windows 已知文件夹接口，
        这样老师把下载位置改到别的盘也能找到。
        """
        custom = str(self.cfg.get("downloads_path") or "").strip()
        if custom:
            if os.path.isdir(custom):
                return custom
            _log("设置的下载目录不可用：%s" % custom)
        try:
            path = winapi.get_downloads_path()
        except Exception:
            path = ""
        if path and os.path.isdir(path):
            return path
        return ""

    def _sync_downloads_watcher(self):
        """按配置启动 / 停止 / 更新下载文件夹监视。返回实际监视的目录。"""
        if not self.downloads_enabled():
            if self.dl_watcher:
                self.dl_watcher.stop()
                self.dl_watcher = None
            self.downloads = ""
            return ""
        path = self.resolve_downloads_path()
        self.downloads = path
        if not path:
            _log("找不到下载文件夹，已跳过监视")
            if self.dl_watcher:
                self.dl_watcher.stop()
                self.dl_watcher = None
            return ""
        if self.dl_watcher and self.dl_watcher.desktop_path == path:
            self.dl_watcher.set_paused(bool(self.cfg.get("paused")))
            self.dl_watcher.set_interval(float(self.cfg.get("watch_interval") or 1.0))
            return path
        if self.dl_watcher:
            self.dl_watcher.stop()
        self.dl_watcher = DesktopWatcher(
            path,
            interval=float(self.cfg.get("watch_interval") or 1.0),
            on_new_file=lambda p, s, m: self._on_new_file(p, s, m, "下载"),
            on_error=lambda e: _log("监视下载文件夹出错：%r" % (e,)))
        self.dl_watcher.set_paused(bool(self.cfg.get("paused")))
        self.dl_watcher.start()
        _log("启动：同时监视下载文件夹 = %s" % path)
        return path

    def _start_detect_worker(self):
        t = threading.Thread(target=self._detect_loop, name="dsr-detect",
                             daemon=True)
        t.start()
        self._workers.append(t)

    def _sync_autostart(self):
        """让注册表状态与配置一致。"""
        want = bool(self.cfg.get("autostart"))
        cur = winapi.get_autostart_command()
        if want and not cur:
            ok, err = winapi.set_autostart(True)
            if not ok:
                _log("设置开机自启动失败：%s" % err)
        elif not want and cur:
            winapi.set_autostart(False)

    # =============================================================== 关闭
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        _log("退出")
        try:
            if self.watcher:
                self.watcher.stop()
            if self.dl_watcher:
                self.dl_watcher.stop()
        except Exception:
            pass
        try:
            if self.ui_thread and self.ui_thread.ready.is_set():
                self.ui_thread.call(lambda: self.bubbles.close_all(), 2.0)
                self.ui_thread.call(lambda: self.tray.destroy(), 2.0)
                self.ui_thread.stop(2.0)
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    # ============================================================ 线程桥
    def _ui(self, fn):
        """把 fn 丢到 tkinter 主线程执行。"""
        self._ui_q.put(fn)

    def _pump_ui(self):
        while True:
            try:
                fn = self._ui_q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                _log(traceback.format_exc())
        if not self._closing:
            self.root.after(120, self._pump_ui)

    def _spawn(self, fn, *a, **kw):
        t = threading.Thread(target=self._guard, args=(fn, a, kw), daemon=True)
        t.start()
        return t

    def _guard(self, fn, a, kw):
        try:
            fn(*a, **kw)
        except Exception:
            _log(traceback.format_exc())

    # ============================================================ 托盘命令
    def _on_tray_command(self, cmd):
        if cmd == winapi.IDM_SHOW:
            self._ui(self.open_main)
        elif cmd == winapi.IDM_SETTINGS:
            self._ui(self.open_settings)
        elif cmd == winapi.IDM_EXIT:
            self._ui(self.shutdown)
        elif cmd == winapi.IDM_OPEN_DESKTOP:
            self.open_desktop()
        elif cmd == winapi.IDM_CHECK:
            self._spawn(self.check_now)
        elif cmd == winapi.IDM_PAUSE:
            self._ui(self.toggle_pause)

    # ============================================================ 状态切换
    def set_paused(self, paused):
        self.cfg["paused"] = bool(paused)
        config.save(self.cfg)
        if self.watcher:
            self.watcher.set_paused(paused)
        if self.dl_watcher:
            self.dl_watcher.set_paused(paused)
        if self.tray:
            self.ui_thread.post(lambda: self.tray.set_paused(paused))
        self.refresh_main()

    def toggle_pause(self):
        self.set_paused(not self.cfg.get("paused"))

    def open_desktop(self):
        try:
            os.startfile(self.desktop)          # noqa: S606
        except Exception as e:  # noqa: BLE001
            _log("打开桌面失败：%r" % (e,))

    def open_downloads(self):
        p = self.downloads or self.resolve_downloads_path()
        if not p:
            self.open_desktop()
            return
        try:
            os.startfile(p)                     # noqa: S606
        except Exception as e:  # noqa: BLE001
            _log("打开下载文件夹失败：%r" % (e,))

    def open_subject_folder(self, subject):
        d = os.path.join(self.desktop, subject)
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)                     # noqa: S606
        except Exception as e:  # noqa: BLE001
            _log("打开科目文件夹失败：%r" % (e,))

    # ============================================================ 主界面
    def open_main(self):
        from .ui_main import MainWindow
        if self.main_window and self.main_window.alive():
            self.main_window.show()
            return
        self.main_window = MainWindow(self)
        self.main_window.show()

    def open_settings(self):
        from .ui_settings import SettingsWindow
        if self.settings_window and self.settings_window.alive():
            self.settings_window.show()
            return
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()

    def refresh_main(self):
        if self.main_window and self.main_window.alive():
            try:
                self.main_window.refresh()
            except Exception:
                pass

    def apply_config(self, new_cfg):
        """设置界面保存后调用。"""
        old_desktop = self.desktop
        old_interval = self.watcher.interval if self.watcher else 1.0
        self.cfg.update(new_cfg)
        config.save(self.cfg)
        self.desktop = self.cfg.get("desktop_path") or winapi.get_desktop_path()
        if self.watcher:
            self.watcher.set_paused(bool(self.cfg.get("paused")))
            if abs(float(self.cfg.get("watch_interval") or 1.0) - old_interval) > 1e-6:
                self.watcher.set_interval(float(self.cfg["watch_interval"]))
            if self.desktop != old_desktop:
                self.watcher.set_desktop(self.desktop)
            if self.dl_watcher:
                self.dl_watcher.set_interval(float(self.cfg.get("watch_interval") or 1.0))
        self._sync_downloads_watcher()
        self._sync_autostart()
        if self.tray:
            self.ui_thread.post(
                lambda: self.tray.set_paused(bool(self.cfg.get("paused"))))
        self.refresh_main()

    # ============================================================ 新文件
    def _on_new_file(self, path, size, mtime, origin="桌面"):
        if self._closing:
            return
        now = time.time()
        if now - self._recent.get(path, 0) < 30:
            return
        self._recent[path] = now
        if len(self._recent) > 200:
            for k in sorted(self._recent, key=self._recent.get)[:100]:
                self._recent.pop(k, None)
        self._detect_q.put((path, size, mtime, origin))

    def _detect_loop(self):
        while True:
            item = self._detect_q.get()
            if item is None:
                return
            try:
                self._handle_new_file(*item)
            except Exception:
                _log(traceback.format_exc())

    def _handle_new_file(self, path, size, mtime, source="桌面"):
        if self.cfg.get("paused"):
            return
        name = os.path.basename(path)
        mode = self.cfg.get("detect_mode", "smart")

        # 快捷方式、临时文件一律不打扰
        if config.is_shortcut(name):
            _log("忽略（快捷方式）：%s" % name)
            return

        kind = config.file_kind(name)
        scoped = config.in_scope(name, self.cfg)

        src_drive = None
        if source == "桌面" and mode in ("smart", "usb"):
            found = usbscan.find_source(name, size)
            src_drive = found[0] if found else None
        from_usb = bool(src_drive)

        subject, reason = config.suggest_subject(name, self.cfg)
        kw_subject, kw_score = config.keyword_hit(name, self.cfg)

        # ClassIsland 联动：正在上的课优先于文件名推断
        lesson_subject = None
        if self.cfg.get("classisland_enabled"):
            info = lesson.current()
            if info:
                lesson_subject = info["subject"]
                subject = lesson_subject
                reason = "来自 ClassIsland 当前课程"

        # 认不出科目时，是否值得开口问老师
        ask = (not subject) and scoped and bool(self.cfg.get("ask_unknown", True))

        if mode == "usb":
            if not from_usb:
                _log("忽略（非 U 盘来源）：%s" % name)
                return
        elif mode == "smart":
            if not (from_usb or subject or ask):
                _log("忽略（无明确科目特征，且「%s」不在关注类型内）：%s"
                     % (config.kind_label(kind), name))
                return
        elif mode == "off":
            return

        origin = ("U 盘 %s" % src_drive.rstrip("\\")) if from_usb else source
        if (lesson_subject and scoped
                and self.cfg.get("classisland_auto")):
            _log("自动归档：%s（来源 %s）→ %s（ClassIsland 当前课程）"
                 % (name, origin, subject))
            self._spawn(self._move_file, path, subject, origin)
            return
        if subject:
            _log("提醒：%s（来源 %s，建议 %s）" % (name, origin, subject))
            self._show_file_bubble(path, size, subject, reason, origin, kind)
        elif ask:
            _log("询问：%s（来源 %s，%s，未认出科目）"
                 % (name, origin, config.kind_label(kind)))
            self._show_ask_bubble(path, size, origin, kind)
        else:
            _log("忽略（无明确科目特征）：%s" % name)

    # ============================================================ 气泡
    def _character_path(self):
        """取当前形象的立绘；配了多张时每调一次换一张（用于气泡轮换）。"""
        cid = self.cfg.get("character") or "teacher_f"
        files = paths.character_files(cid)
        if not files:
            try:
                files = [paths.builtin_characters()[0][2]]
            except Exception:
                return None
        idx = self._char_rot % len(files)
        self._char_rot += 1
        return files[idx]

    def _play_sound(self):
        if not self.cfg.get("sound", True):
            return
        try:
            import winsound
            winsound.PlaySound("SystemAsterisk",
                               winsound.SND_ALIAS | winsound.SND_ASYNC)
        except Exception:
            pass

    def _show(self, spec, duration=None, on_action=None):
        if not self.bubbles:
            return
        corner = self.cfg.get("corner", "br")
        spec = dict(spec)
        spec.setdefault("accent", "#2F855A")
        spec["character_path"] = self._character_path()
        spec["flip"] = corner in ("bl", "tl")
        dur = float(duration if duration is not None
                    else (self.cfg.get("duration") or 14))
        self._play_sound()

        def do():
            try:
                self.bubbles.show(spec, corner=corner, duration=dur,
                                  on_action=on_action)
            except Exception:
                _log(traceback.format_exc())

        if self.ui_thread and self.ui_thread.ready.is_set():
            self.ui_thread.post(do)
        else:
            _log("气泡未显示：UI 线程未就绪（ready=%s）"
                 % (self.ui_thread.ready.is_set() if self.ui_thread else None))

    def _show_file_bubble(self, path, size, subject, reason, origin, kind=""):
        name = os.path.basename(path)
        body = ["《%s》" % config.short_name(name, 34),
                "大小 %s · 来自 %s" % (config.human_size(size), origin)]
        buttons = []
        exists = config.subject_exists(self.cfg, subject) if subject else False
        if subject and self.cfg.get("show_move_button", True):
            label = ("移动到「%s」" % subject) if exists else ("新建「%s」并移入" % subject)
            buttons.append({"id": "move", "text": label, "kind": "primary"})
        if self.cfg.get("show_open_button", True):
            buttons.append({"id": "other", "text": "放置在其他文件夹", "kind": "ghost"})
        buttons.append({"id": "dismiss", "text": "稍后处理", "kind": "ghost"})

        if subject:
            hint = ("建议归档到「%s」文件夹 · %s" % (subject, reason)) if reason \
                else ("建议归档到「%s」文件夹" % subject)
            title = "老师好呀，发现一个新文件"
        else:
            hint = "暂时没认出科目，可在设置里补充关键词"
            title = "老师好呀，这个文件放哪儿呢"
        body.append("")

        spec = {
            "title": title,
            "body": body,
            "hint": hint,
            "buttons": buttons,
            "accent": "#2F855A" if subject else "#B7791F",
        }

        def action(aid, win):
            if aid == "move" and subject:
                win.begin_close()
                self._spawn(self._move_file, path, subject, origin)
            elif aid == "other":
                win.begin_close()
                self._ui(lambda: self.open_picker(path, size, origin, kind))

        self._show(spec, on_action=action)

    # ---------------------------------------------------- 认不出科目时询问
    def _show_ask_bubble(self, path, size, origin, kind):
        """认不出科目：问老师这个文件该放进哪个文件夹。"""
        name = os.path.basename(path)
        body = ["《%s》" % config.short_name(name, 34),
                "大小 %s · 来自 %s · %s"
                % (config.human_size(size), origin, config.kind_label(kind)),
                ""]
        buttons = [{"id": "pick", "text": "选择文件夹…", "kind": "primary"},
                   {"id": "open", "text": "打开桌面", "kind": "ghost"},
                   {"id": "dismiss", "text": "稍后处理", "kind": "ghost"}]
        spec = {
            "title": "老师，这个文件放在哪儿呢？",
            "body": body,
            "hint": "我没认出它属于哪一科，帮我选一个文件夹吧",
            "buttons": buttons,
            "accent": "#B7791F",
        }

        def action(aid, win):
            if aid == "pick":
                win.begin_close()
                self._ui(lambda: self.open_picker(path, size, origin, kind))
            elif aid == "open":
                win.begin_close()
                self.open_desktop()

        self._show(spec, on_action=action)

    def open_picker(self, path, size=0, origin="", kind="", on_done=None):
        """打开「选择归档文件夹」窗口（必须在 tkinter 主线程调用）。"""
        from .ui_pick import FolderPicker
        if self.picker_window and self.picker_window.alive():
            self.picker_window.set_file(path, size, origin, kind, on_done)
            self.picker_window.show()
            return
        try:
            self.picker_window = FolderPicker(self, path, size, origin, kind,
                                              on_done)
        except Exception:
            _log(traceback.format_exc())
            return
        self.picker_window.show()

    def place_file(self, src, subject, origin="", remember_ext=False):
        """老师选好文件夹后：记下选择（可选）并把文件移过去。"""
        if remember_ext and subject:
            if config.remember_ext_subject(self.cfg, src, subject):
                config.save(self.cfg)
                _log("记住类型映射：%s -> %s"
                     % (config.file_ext(src) or "?", subject))
        self._spawn(self._move_file, src, subject, origin)

    def _unique_target(self, dst_dir, filename):
        target = os.path.join(dst_dir, filename)
        if not os.path.exists(target):
            return target
        stem, ext = os.path.splitext(filename)
        for i in range(2, 1000):
            cand = os.path.join(dst_dir, "%s (%d)%s" % (stem, i, ext))
            if not os.path.exists(cand):
                return cand
        return target

    def _move_file(self, src, subject, origin=""):
        where = "下载文件夹" if origin == "下载" else "桌面"
        if not os.path.exists(src):
            self._show({
                "title": "咦，文件不见了",
                "body": ["《%s》已经不在%s里了。" % (config.short_name(
                    os.path.basename(src)), where)],
                "hint": "可能已经被移动或删除",
                "buttons": [{"id": "dismiss", "text": "知道了", "kind": "primary"}],
                "accent": "#B7791F",
            }, duration=8)
            return
        dst_dir = os.path.join(self.desktop, subject)
        try:
            os.makedirs(dst_dir, exist_ok=True)
            target = self._unique_target(dst_dir, os.path.basename(src))
            shutil.move(src, target)
        except Exception as e:  # noqa: BLE001
            _log("移动失败：%r" % (e,))
            self._show({
                "title": "没能移过去",
                "body": ["《%s》" % config.short_name(os.path.basename(src)),
                         "目标：%s" % subject, "原因：%s" % e],
                "hint": "可以手动拖进对应文件夹",
                "buttons": [
                    {"id": "open", "text": "打开桌面", "kind": "primary"},
                    {"id": "dismiss", "text": "知道了", "kind": "ghost"},
                ],
                "accent": "#C53030",
            }, duration=16, on_action=lambda aid, win: (
                win.begin_close(), self.open_desktop())
                if aid == "open" else None)
            return

        config.append_history(os.path.basename(src), subject)
        if self.watcher:
            self.watcher.rescan()
        if self.dl_watcher:
            self.dl_watcher.rescan()
        _log("已移动：%s -> %s" % (src, target))
        self._show({
            "title": "搞定啦！",
            "body": ["《%s》" % config.short_name(os.path.basename(src)),
                     "已经放进「%s」文件夹。" % subject],
            "hint": "点下面的按钮可以打开看看",
            "buttons": [
                {"id": "open", "text": "打开「%s」" % subject, "kind": "primary"},
                {"id": "dismiss", "text": "好", "kind": "ghost"},
            ],
            "accent": "#2F855A",
        }, duration=9, on_action=lambda aid, win: (
            win.begin_close(), self.open_subject_folder(subject))
            if aid == "open" else None)

    # ============================================================ 立即检测
    def check_now(self):
        if self.cfg.get("paused"):
            self._show({
                "title": "现在是暂停状态哦",
                "body": ["提醒已经被暂停了。"],
                "hint": "可以在托盘菜单或主界面里继续提醒",
                "buttons": [{"id": "dismiss", "text": "知道了", "kind": "primary"}],
                "accent": "#B7791F",
            }, duration=8)
            return
        items = []      # (full, name, subject, 来源)
        unknown = []    # (full, 来源)
        folders = [(self.desktop, "桌面")]
        if self.downloads_enabled():
            dl = self.downloads or self.resolve_downloads_path()
            if dl and dl != self.desktop:
                folders.append((dl, "下载"))
        for folder, source in folders:
            try:
                for entry in sorted(os.listdir(folder)):
                    full = os.path.join(folder, entry)
                    if not os.path.isfile(full):
                        continue
                    if entry.startswith(".") or entry.startswith("~"):
                        continue
                    if entry.lower() in ("desktop.ini", "thumbs.db"):
                        continue
                    if config.is_shortcut(entry):
                        continue
                    subject, reason = config.suggest_subject(entry, self.cfg)
                    if subject:
                        items.append((full, entry, subject, source))
                    elif config.in_scope(entry, self.cfg) \
                            and self.cfg.get("ask_unknown", True):
                        unknown.append((full, source))
            except Exception:
                _log(traceback.format_exc())
        if not items and not unknown:
            self._show({
                "title": "文件夹很整洁",
                "body": ["没有发现需要归档的文件。"],
                "hint": "把 U 盘里的文件复制到桌面，或下载新文件，我会立刻提醒您",
                "buttons": [{"id": "dismiss", "text": "好的", "kind": "primary"}],
                "accent": "#2F855A",
            }, duration=10)
            return
        buttons = []
        if items:
            buttons.append({"id": "archive", "text": "全部归档", "kind": "primary"})
        if unknown:
            buttons.append({"id": "pick", "text": "逐个选择…", "kind": "primary"})
        buttons.append({"id": "dismiss", "text": "稍后", "kind": "ghost"})

        names = ["《%s》→「%s」" % (config.short_name(n, 22), s)
                 for _f, n, s, _o in items[:4]]
        if len(items) > 4:
            names.append("…还有 %d 个" % (len(items) - 4))
        for full, _src in unknown[:3]:
            names.append("《%s》→ 需要您指定文件夹"
                         % config.short_name(os.path.basename(full), 22))
        if len(unknown) > 3:
            names.append("…还有 %d 个需要指定" % (len(unknown) - 3))
        title = "发现 %d 个文件还没归档" % (len(items) + len(unknown))
        spec = {
            "title": title,
            "body": names,
            "hint": ("需要我一次性把它们放进对应科目文件夹吗"
                     if not unknown else "认不出的文件需要您帮我选一下文件夹"),
            "buttons": buttons,
            "accent": "#B7791F",
        }

        def action(aid, win):
            if aid == "archive":
                win.begin_close()
                self._spawn(self._archive_all, items)
            elif aid == "pick":
                win.begin_close()
                queue = list(unknown)
                state = {"first": True}

                def step(subject=None):
                    if not state["first"] and not subject:
                        return          # 老师按了取消，不再追问下一个
                    state["first"] = False
                    while queue:
                        nxt, src_origin = queue.pop(0)
                        if not os.path.exists(nxt):
                            continue
                        try:
                            size = os.path.getsize(nxt)
                        except OSError:
                            size = 0
                        self.open_picker(
                            nxt, size, src_origin,
                            config.file_kind(os.path.basename(nxt)),
                            on_done=step)
                        return

                self._ui(step)

        self._show(spec, duration=20, on_action=action)

    def _archive_all(self, items):
        done = 0
        fail = 0
        for full, name, subject, _origin in items:
            try:
                dst_dir = os.path.join(self.desktop, subject)
                os.makedirs(dst_dir, exist_ok=True)
                target = self._unique_target(dst_dir, name)
                shutil.move(full, target)
                config.append_history(name, subject)
                done += 1
            except Exception as e:  # noqa: BLE001
                _log("归档失败 %s：%r" % (name, e))
                fail += 1
        if self.watcher:
            self.watcher.rescan()
        if self.dl_watcher:
            self.dl_watcher.rescan()
        body = ["成功归档 %d 个文件" % done]
        if fail:
            body.append("有 %d 个没能移动" % fail)
        self._show({
            "title": "批量归档完成",
            "body": body,
            "hint": "打开桌面可以检查一下",
            "buttons": [
                {"id": "open", "text": "打开桌面", "kind": "primary"},
                {"id": "dismiss", "text": "好", "kind": "ghost"},
            ],
            "accent": "#2F855A",
        }, duration=12, on_action=lambda aid, win: (
            win.begin_close(), self.open_desktop())
            if aid == "open" else None)

    # ============================================================ 首启动
    def first_run_greeting(self):
        self._show({
            "title": "老师您好，我是提醒小助手",
            "body": ["以后您把 U 盘里的文件复制到桌面，",
                     "我就会跳出来提醒您归档到对应的科目文件夹。"],
            "hint": "单击右下角托盘图标可以打开主界面或退出",
            "buttons": [
                {"id": "main", "text": "打开主界面", "kind": "primary"},
                {"id": "dismiss", "text": "知道啦", "kind": "ghost"},
            ],
            "accent": "#2B6CB0",
        }, duration=18, on_action=lambda aid, win: (
            win.begin_close(), self._ui(self.open_main))
            if aid == "main" else None)
