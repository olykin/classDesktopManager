# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""设置界面。"""
from __future__ import annotations

import copy
import os
import tkinter as tk
from tkinter import messagebox, simpledialog

from . import config, lesson, paths, winapi
from .uishared import (ACCENT, ACCENT_D, BG, BORDER, CARD, DANGER, MUTED, OK,
                       SOFT, TEXT, WARN, ScrollFrame,
                       center as _center, font as _font, px, short_path)

WA = winapi.work_area()
W = min(px(620), int(WA[2] * 0.92))
H = min(px(720), int((WA[3] - WA[1]) * 0.94))

CORNERS = [("br", "右下角（推荐）"), ("bl", "左下角"),
           ("tr", "右上角"), ("tl", "左上角")]

MODES = [("smart", "智能"), ("usb", "仅 U 盘"), ("all", "所有新文件")]


class FlatButton(tk.Button):
    def __init__(self, master, text, command, kind="ghost", **kw):
        colors = {
            "primary": (ACCENT, "#FFFFFF", ACCENT_D),
            "ghost": ("#FFFFFF", TEXT, "#E8EEF6"),
            "danger": ("#FFFFFF", DANGER, "#FBEAEA"),
        }[kind]
        bg, fg, active = colors
        super().__init__(master, text=text, command=command, bg=bg, fg=fg,
                         activebackground=active, activeforeground=fg,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER if kind == "ghost" else bg,
                         highlightcolor=BORDER if kind == "ghost" else bg,
                         font=_font(10, kind == "primary"), cursor="hand2",
                         padx=px(14), pady=px(6), **kw)


class SettingsWindow:
    def __init__(self, app):
        self.app = app
        self.cfg = copy.deepcopy(app.cfg)
        self.win = tk.Toplevel(app.root)
        self.win.title("设置 - %s" % paths.APP_NAME)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.hide)
        try:
            self.win.iconbitmap(paths.asset_path("app.ico"))
        except Exception:
            pass
        self._char_imgs = []
        self._build()
        _center(self.win, W, H, bias=5)
        self.win.bind("<MouseWheel>", self._on_wheel)

    # ------------------------------------------------------------ 基础
    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:
            return False

    def show(self):
        if self.alive():
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _var(self, key, default=None):
        val = self.cfg.get(key, config.DEFAULTS.get(key, default))
        if isinstance(config.DEFAULTS.get(key), bool):
            return tk.BooleanVar(value=bool(val))
        return tk.Variable(value=val)

    # ------------------------------------------------------------ 构建
    def _build(self):
        head = tk.Frame(self.win, bg=ACCENT, height=px(72))
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="设置", bg=ACCENT, fg="#FFFFFF",
                 font=_font(15, True)).pack(anchor="w", padx=px(18),
                                            pady=(px(10), 0))
        tk.Label(head, text="修改后记得点击底部的「保存设置」",
                 bg=ACCENT, fg="#D6E4F5", font=_font(9)).pack(
            anchor="w", padx=px(18))

        wrap = ScrollFrame(self.win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=px(14), pady=px(10))
        self.scroll = wrap
        wrap = wrap.body

        self.v_autostart = self._var("autostart")
        self.v_start_min = self._var("start_minimized")
        self.v_close_tray = self._var("close_to_tray")
        self.v_sound = self._var("sound")
        self.v_move = self._var("show_move_button")
        self.v_open = self._var("show_open_button")
        self.v_paused = tk.BooleanVar(value=bool(self.cfg.get("paused")))
        self.v_character = tk.StringVar(value=self.cfg.get("character", "teacher_f"))
        self.v_corner = tk.StringVar(value=self.cfg.get("corner", "br"))
        self.v_mode = tk.StringVar(value=self.cfg.get("detect_mode", "smart"))
        self.v_duration = tk.IntVar(value=int(self.cfg.get("duration") or 14))
        self.v_ask = self._var("ask_unknown")
        self.v_force = self._var("force_archive")
        self.v_kinds = {}
        _cur_kinds = config.auto_kinds(self.cfg)
        for _k, _label in config.AUTO_KIND_CHOICES:
            self.v_kinds[_k] = tk.BooleanVar(value=_k in _cur_kinds)

        c1 = self._card(wrap, "常规")
        self._check(c1, "开机自动启动（登录 Windows 后自动在托盘运行）",
                    self.v_autostart)
        self._check(c1, "启动后直接最小化到系统托盘", self.v_start_min)
        self._check(c1, "关闭主窗口时最小化到托盘（不退出）", self.v_close_tray)
        self._check(c1, "弹出提醒时播放提示音", self.v_sound)
        self._check(c1, "暂停所有提醒", self.v_paused)
        self._check(c1, "强制要求归档（去掉「稍后处理」与气泡右上角关闭键）",
                    self.v_force)
        tk.Label(c1,
                 text="开启后归档提醒不会自动消失，必须选一个科目文件夹；"
                      "关闭后恢复「稍后处理」与关闭键。",
                 bg=CARD, fg=MUTED, font=_font(8), anchor="w", justify="left",
                 wraplength=px(540)).pack(anchor="w", padx=px(14),
                                           pady=(0, px(6)))

        c2 = self._card(wrap, "提醒方式")
        row = tk.Frame(c2, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=(px(2), px(6)))
        tk.Label(row, text="检测范围", bg=CARD, fg=TEXT, font=_font(10),
                 width=9, anchor="w").pack(side="left")
        for val, text in MODES:
            tk.Radiobutton(row, text=text, value=val, variable=self.v_mode,
                           bg=CARD, fg=TEXT, font=_font(10), anchor="w",
                           activebackground=CARD, selectcolor="#FFFFFF",
                           highlightthickness=0,
                           cursor="hand2").pack(side="left", padx=(0, px(10)))

        row = tk.Frame(c2, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=px(4))
        tk.Label(row, text="气泡位置", bg=CARD, fg=TEXT, font=_font(10),
                 width=9, anchor="w").pack(side="left")
        for val, text in CORNERS:
            tk.Radiobutton(row, text=text, value=val, variable=self.v_corner,
                           bg=CARD, fg=TEXT, font=_font(10),
                           activebackground=CARD, selectcolor="#FFFFFF",
                           highlightthickness=0,
                           cursor="hand2").pack(side="left", padx=(0, px(8)))

        row = tk.Frame(c2, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=(px(4), px(2)))
        tk.Label(row, text="停留时长", bg=CARD, fg=TEXT, font=_font(10),
                 width=9, anchor="w").pack(side="left")
        self.lbl_dur = tk.Label(row, text="%d 秒" % self.v_duration.get(),
                                bg=CARD, fg=ACCENT, font=_font(10, True), width=6)
        self.lbl_dur.pack(side="right")
        tk.Scale(row, from_=5, to=60, orient="horizontal",
                 variable=self.v_duration, bg=CARD, fg=TEXT, font=_font(8),
                 highlightthickness=0, bd=0, showvalue=False,
                 activebackground=ACCENT, troughcolor="#E3EAF3",
                 length=px(340), command=self._on_dur).pack(
            side="left", fill="x", expand=True)

        row = tk.Frame(c2, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=(px(4), px(10)))
        self._check(row, "气泡里显示「移动到科目文件夹」按钮", self.v_move,
                    side="left")
        self._check(row, "显示「放置在其他文件夹」按钮", self.v_open, side="left")

        # ---- 下载文件夹
        c_dl = self._card(wrap, "下载文件夹")
        self.v_downloads = self._var("watch_downloads")
        self._check(c_dl, "同时监视下载文件夹（默认关闭）", self.v_downloads)
        tk.Label(c_dl,
                 text="开启后，新下载的文件会像桌面文件一样弹出归档提醒。"
                      "Windows 的下载位置改过也能自动找到；找不到时可以手动指定。",
                 bg=CARD, fg=MUTED, font=_font(8), anchor="w", justify="left",
                 wraplength=px(540)).pack(anchor="w", padx=px(14),
                                           pady=(0, px(6)))
        dlrow = tk.Frame(c_dl, bg=CARD)
        dlrow.pack(fill="x", padx=px(14), pady=(0, px(12)))
        tk.Label(dlrow, text="下载目录", bg=CARD, fg=TEXT, font=_font(9),
                 width=8, anchor="w").pack(side="left")
        self.lbl_dl = tk.Label(dlrow, text="", bg=CARD, fg=TEXT, font=_font(9),
                               anchor="w", justify="left")
        self.lbl_dl.pack(side="left", fill="x", expand=True)
        FlatButton(dlrow, "更改…", self._pick_downloads).pack(side="right")
        FlatButton(dlrow, "自动定位", self._use_auto_downloads).pack(
            side="right", padx=px(6))
        self._refresh_dl_label()

        # ---- ClassIsland 课程联动
        c_ci = self._card(wrap, "ClassIsland 课程联动")
        self.v_lesson = self._var("classisland_enabled")
        self._check(c_ci, "按 ClassIsland 当前课程建议归档科目（默认关闭）",
                    self.v_lesson)
        self.v_lesson_auto = self._var("classisland_auto")
        self._check(c_ci, "上课时直接归档到对应科目文件夹，不再弹气泡",
                    self.v_lesson_auto)
        tk.Label(c_ci,
                 text="需要在 ClassIsland 里安装「classDesktopManager 课程联动」"
                      "插件。插件只在本机写一个状态文件，不上传任何数据；"
                      "关掉 ClassIsland 或超过一分钟没更新就自动忽略。",
                 bg=CARD, fg=MUTED, font=_font(8), anchor="w", justify="left",
                 wraplength=px(540)).pack(anchor="w", padx=px(14),
                                           pady=(0, px(6)))
        cirow = tk.Frame(c_ci, bg=CARD)
        cirow.pack(fill="x", padx=px(14), pady=(0, px(12)))
        self.lbl_ci = tk.Label(cirow, text="", bg=CARD, fg=TEXT, font=_font(9),
                               anchor="w", justify="left")
        self.lbl_ci.pack(side="left", fill="x", expand=True)
        FlatButton(cirow, "刷新状态", self._refresh_ci_label).pack(side="right")
        self._refresh_ci_label()

        # ---- 关注哪些文件
        c3 = self._card(wrap, "关注哪些文件")
        tk.Label(c3, text="快捷方式（.lnk / .url）和临时文件永远不会打扰您。",
                 bg=CARD, fg=MUTED, font=_font(8), anchor="w").pack(
            anchor="w", padx=px(14), pady=(0, px(4)))
        for kind, label in config.AUTO_KIND_CHOICES:
            self._check(c3, label, self.v_kinds[kind])
        self._check(c3, "认不出科目时，弹气泡问我该放进哪个文件夹",
                    self.v_ask)
        tk.Frame(c3, bg=CARD, height=px(6)).pack()

        c4 = self._card(wrap, "提示人物")
        box = tk.Frame(c4, bg=CARD)
        box.pack(fill="x", padx=px(14), pady=(px(2), px(8)))
        imgs = self._load_char_thumbs()
        for cid, name, path in paths.builtin_characters():
            cell = tk.Frame(box, bg=CARD)
            cell.pack(side="left", padx=(0, px(10)))
            img = imgs.get(cid)
            if img is not None:
                lbl = tk.Label(cell, image=img, bg=CARD, cursor="hand2",
                               highlightthickness=2, highlightbackground=BORDER)
                lbl.image = img
            else:
                lbl = tk.Label(cell, text="(无预览)", bg=CARD, fg=MUTED,
                               font=_font(8), width=10, height=5)
            lbl.pack()
            tk.Radiobutton(cell, text=name, value=cid,
                           variable=self.v_character, bg=CARD, fg=TEXT,
                           font=_font(9), activebackground=CARD,
                           selectcolor="#FFFFFF", highlightthickness=0,
                           cursor="hand2").pack()
            lbl.bind("<Button-1>", lambda e, c=cid: self.v_character.set(c))
        FlatButton(c4, "预览气泡效果", self._preview, "ghost").pack(
            anchor="w", padx=px(14), pady=(0, px(10)))

        c5 = self._card(wrap, "科目文件夹（桌面上的子文件夹）")
        holder = tk.Frame(c5, bg=CARD)
        holder.pack(fill="both", expand=True, padx=px(14), pady=(px(2), px(6)))
        self.lst = tk.Listbox(holder, bg=SOFT, fg=TEXT, font=_font(10),
                              relief="flat", bd=0, highlightthickness=0,
                              height=6, selectbackground="#DCE9F7",
                              selectforeground=TEXT, activestyle="none")
        sb = tk.Scrollbar(holder, command=self.lst.yview, relief="flat",
                          bd=0, width=px(12))
        self.lst.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lst.pack(side="left", fill="both", expand=True)
        self.lst.bind("<Double-Button-1>", lambda e: self._edit_subject())

        brow = tk.Frame(c5, bg=CARD)
        brow.pack(fill="x", padx=px(14), pady=(0, px(12)))
        FlatButton(brow, "添加", self._add_subject).pack(side="left")
        FlatButton(brow, "编辑", self._edit_subject).pack(side="left", padx=px(6))
        FlatButton(brow, "删除", self._del_subject, "danger").pack(side="left")
        FlatButton(brow, "从桌面重新读取", self._import_subjects).pack(
            side="left", padx=px(6))

        foot = tk.Frame(self.win, bg=BG)
        foot.pack(fill="x", padx=px(14), pady=(0, px(12)))
        FlatButton(foot, "保存设置", self.save, "primary").pack(side="right")
        FlatButton(foot, "取消", self.hide).pack(side="right", padx=px(8))
        FlatButton(foot, "恢复默认", self._reset).pack(side="left")

        self._reload_subjects()

    def _card(self, parent, title):
        outer = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER)
        outer.pack(fill="x", pady=(0, px(10)))
        tk.Label(outer, text=title, bg=CARD, fg=MUTED,
                 font=_font(9, True)).pack(anchor="w", padx=px(14),
                                           pady=(px(10), px(4)))
        return outer

    def _check(self, parent, text, var, side=None):
        cb = tk.Checkbutton(parent, text=text, variable=var, bg=CARD, fg=TEXT,
                            font=_font(10), anchor="w", activebackground=CARD,
                            selectcolor="#FFFFFF", highlightthickness=0,
                            cursor="hand2")
        if side:
            cb.pack(side=side, padx=(px(14) if side == "left" else 0, px(8)),
                    pady=(0, px(4)))
        else:
            cb.pack(anchor="w", padx=px(14), pady=px(2))
        return cb

    def _on_dur(self, _v):
        self.lbl_dur.configure(text="%d 秒" % self.v_duration.get())

    def _on_wheel(self, ev):
        self.scroll.on_wheel(ev)

    # -------------------------------------------------------- 下载文件夹
    def _downloads_display(self):
        custom = str(self.cfg.get("downloads_path") or "").strip()
        path = custom or winapi.get_downloads_path()
        if not path or not os.path.isdir(path):
            return "（没找到，请点「更改…」指定）"
        return short_path(path, 46)

    def _refresh_dl_label(self):
        self.lbl_dl.configure(text=self._downloads_display())

    def _pick_downloads(self):
        from tkinter import filedialog
        cur = (str(self.cfg.get("downloads_path") or "").strip()
               or winapi.get_downloads_path())
        chosen = filedialog.askdirectory(
            parent=self.win, title="选择下载文件夹",
            initialdir=cur if os.path.isdir(cur) else None)
        if not chosen:
            return
        self.cfg["downloads_path"] = os.path.normpath(chosen)
        self._refresh_dl_label()

    def _use_auto_downloads(self):
        self.cfg["downloads_path"] = ""
        self._refresh_dl_label()

    # ------------------------------------------------- ClassIsland 联动
    def _refresh_ci_label(self):
        try:
            text = lesson.describe()
        except Exception:
            text = "无法读取 ClassIsland 状态"
        if not self.v_lesson.get():
            text = "已关闭（开启后才会读取课程）"
        self.lbl_ci.configure(text=text)

    def _load_char_thumbs(self):
        out = {}
        try:
            from PIL import Image, ImageTk
        except Exception:
            return out
        for cid, _name, path in paths.builtin_characters():
            try:
                im = Image.open(path).convert("RGBA")
                im.thumbnail((px(72), px(72)), Image.LANCZOS)
                bg = Image.new("RGBA", im.size, (238, 242, 247, 255))
                bg.alpha_composite(im)
                photo = ImageTk.PhotoImage(bg.convert("RGB"))
                out[cid] = photo
                self._char_imgs.append(photo)
            except Exception:
                continue
        return out

    # ------------------------------------------------------------ 科目
    def _reload_subjects(self):
        self.lst.delete(0, "end")
        desktop = self.cfg.get("desktop_path") or winapi.get_desktop_path()
        for s in self.cfg.get("subjects", []):
            exists = os.path.isdir(os.path.join(desktop, s.get("name", "")))
            kws = "、".join(s.get("keywords", [])[:4])
            self.lst.insert("end", "%s %s   [%s]" % (
                "[已有]" if exists else "[待建]", s.get("name", ""), kws))

    def _selected(self):
        sel = self.lst.curselection()
        if not sel:
            return None, None
        return sel[0], self.cfg["subjects"][sel[0]]

    def _add_subject(self):
        name = simpledialog.askstring("添加科目", "科目文件夹名称：", parent=self.win)
        if not name or not name.strip():
            return
        name = name.strip()
        if name in config.subject_names(self.cfg):
            messagebox.showwarning("重复", "「%s」已经存在了。" % name, parent=self.win)
            return
        kws = simpledialog.askstring(
            "关键词", "用于识别文件的关键词（用逗号分隔，可留空）：",
            parent=self.win) or ""
        entry = config.normalize_subject(name)
        for k in kws.replace("，", ",").split(","):
            k = k.strip()
            if k and k not in entry["keywords"]:
                entry["keywords"].append(k)
        self.cfg["subjects"].append(entry)
        self._reload_subjects()

    def _edit_subject(self):
        idx, entry = self._selected()
        if entry is None:
            messagebox.showinfo("提示", "请先在列表里选择一个科目。", parent=self.win)
            return
        name = simpledialog.askstring("编辑科目", "科目文件夹名称：",
                                      initialvalue=entry.get("name", ""),
                                      parent=self.win)
        if name is None:
            return
        kws = simpledialog.askstring(
            "关键词", "关键词（用逗号分隔）：",
            initialvalue=",".join(entry.get("keywords", [])), parent=self.win)
        if kws is None:
            return
        new = config.normalize_subject(name.strip())
        for k in kws.replace("，", ",").split(","):
            k = k.strip()
            if k and k not in new["keywords"]:
                new["keywords"].append(k)
        self.cfg["subjects"][idx] = new
        self._reload_subjects()

    def _del_subject(self):
        idx, entry = self._selected()
        if entry is None:
            messagebox.showinfo("提示", "请先在列表里选择一个科目。", parent=self.win)
            return
        if messagebox.askyesno("删除", "确定不再监控「%s」吗？（不会删除文件夹）"
                               % entry.get("name", ""), parent=self.win):
            self.cfg["subjects"].pop(idx)
            self._reload_subjects()

    def _import_subjects(self):
        desktop = self.cfg.get("desktop_path") or winapi.get_desktop_path()
        try:
            found = [e for e in sorted(os.listdir(desktop))
                     if os.path.isdir(os.path.join(desktop, e))
                     and not e.startswith(".") and not e.startswith("$")]
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("失败", "读取桌面失败：%s" % e, parent=self.win)
            return
        have = set(config.subject_names(self.cfg))
        added = 0
        for name in found:
            if name in have:
                continue
            self.cfg["subjects"].append(config.normalize_subject(name))
            added += 1
        self._reload_subjects()
        messagebox.showinfo("完成", "从桌面新增了 %d 个科目文件夹。" % added,
                            parent=self.win)

    # ------------------------------------------------------------ 动作
    def _preview(self):
        cid = self.v_character.get()
        spec = {
            "title": "老师好呀，发现一个新文件",
            "body": ["《第三单元数学测试卷.docx》",
                     "大小 128.5 KB · 来自 U 盘 E:\\", ""],
            "hint": "建议归档到「数学」文件夹 · 文件名包含「数学」",
            "buttons": [
                {"id": "move", "text": "移动到「数学」", "kind": "primary"},
                {"id": "other", "text": "放置在其他文件夹", "kind": "ghost"},
                {"id": "dismiss", "text": "稍后处理", "kind": "ghost"},
            ],
            "accent": "#2F855A",
        }
        old = (self.app.cfg.get("character"), self.app.cfg.get("corner"),
               self.cfg.get("desktop_path"))
        self.app.cfg["character"] = cid
        self.app.cfg["corner"] = self.v_corner.get()
        self.app._show(spec, duration=max(8, int(self.v_duration.get())))
        self.app.cfg["character"], self.app.cfg["corner"] = old[0], old[1]

    def _reset(self):
        if not messagebox.askyesno("恢复默认", "确定把所有设置恢复为默认值吗？",
                                   parent=self.win):
            return
        self.cfg = copy.deepcopy(config.DEFAULTS)
        self.cfg["subjects"] = config.build_default_subjects(
            self.cfg.get("desktop_path") or winapi.get_desktop_path())
        self.v_autostart.set(False)
        self.v_start_min.set(True)
        self.v_close_tray.set(True)
        self.v_sound.set(True)
        self.v_move.set(True)
        self.v_open.set(True)
        self.v_character.set("teacher_f")
        self.v_corner.set("br")
        self.v_mode.set("smart")
        self.v_duration.set(14)
        self.v_paused.set(False)
        self.v_ask.set(True)
        self.v_force.set(False)
        self.v_downloads.set(False)
        self.cfg["downloads_path"] = ""
        self.v_lesson.set(False)
        self.v_lesson_auto.set(False)
        self._refresh_ci_label()
        self._refresh_dl_label()
        for k, _l in config.AUTO_KIND_CHOICES:
            self.v_kinds[k].set(k in config.DEFAULTS["auto_kinds"])
        self._reload_subjects()

    def save(self):
        cfg = self.app.cfg
        cfg["autostart"] = bool(self.v_autostart.get())
        cfg["start_minimized"] = bool(self.v_start_min.get())
        cfg["close_to_tray"] = bool(self.v_close_tray.get())
        cfg["sound"] = bool(self.v_sound.get())
        cfg["show_move_button"] = bool(self.v_move.get())
        cfg["show_open_button"] = bool(self.v_open.get())
        cfg["character"] = self.v_character.get()
        cfg["corner"] = self.v_corner.get()
        cfg["detect_mode"] = self.v_mode.get()
        cfg["duration"] = int(self.v_duration.get())
        cfg["paused"] = bool(self.v_paused.get())
        cfg["ask_unknown"] = bool(self.v_ask.get())
        cfg["force_archive"] = bool(self.v_force.get())
        kinds = [k for k, _l in config.AUTO_KIND_CHOICES
                 if self.v_kinds[k].get()]
        cfg["auto_kinds"] = kinds
        cfg["watch_downloads"] = bool(self.v_downloads.get())
        cfg["downloads_path"] = str(self.cfg.get("downloads_path") or "").strip()
        cfg["classisland_enabled"] = bool(self.v_lesson.get())
        cfg["classisland_auto"] = bool(self.v_lesson_auto.get())
        cfg["subjects"] = self.cfg.get("subjects", [])
        cfg["first_run"] = False
        ok, err = config.save(cfg)
        if not ok:
            messagebox.showerror("保存失败", err, parent=self.win)
            return
        self.app.apply_config(cfg)
        self.app._show({
            "title": "设置已保存",
            "body": ["开机自启动：%s" % ("已开启" if cfg["autostart"] else "已关闭"),
                     "下载文件夹监视：%s" % ("已开启" if cfg["watch_downloads"] else "已关闭"),
                     "提示人物：%s" % paths.CHARACTER_NAMES.get(
                         cfg["character"], cfg["character"])],
            "hint": "随时可以在托盘菜单里重新打开设置",
            "buttons": [{"id": "dismiss", "text": "好的", "kind": "primary"}],
            "accent": "#2B6CB0",
        }, duration=6)
        self.hide()
