# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""主界面。"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox

from . import config, paths
from .uishared import (ACCENT, ACCENT_D, BG, BORDER, CARD, DANGER, MUTED, OK,
                       SOFT, TEXT, WARN, center, font as _font, px, short_path)

WIDTH = px(560)
HEIGHT = px(660)


class FlatButton(tk.Button):
    def __init__(self, master, text, command, kind="ghost", width=None, **kw):
        colors = {
            "primary": (ACCENT, "#FFFFFF", ACCENT_D),
            "ghost": ("#FFFFFF", TEXT, "#E8EEF6"),
            "warn": (WARN, "#FFFFFF", "#96601A"),
            "danger": ("#FFFFFF", DANGER, "#FBEAEA"),
        }[kind]
        bg, fg, active = colors
        super().__init__(
            master, text=text, command=command, bg=bg, fg=fg,
            activebackground=active, activeforeground=fg,
            relief="flat", bd=0, highlightthickness=1,
            highlightbackground=BORDER if kind == "ghost" else bg,
            highlightcolor=BORDER if kind == "ghost" else bg,
            font=_font(10, kind == "primary"), cursor="hand2",
            padx=px(14), pady=px(8), **kw)
        if width:
            self.configure(width=width)


class Card(tk.Frame):
    def __init__(self, master, title=None, **kw):
        super().__init__(master, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER, **kw)
        self.body = self
        if title:
            tk.Label(self, text=title, bg=CARD, fg=MUTED,
                     font=_font(9, True)).pack(anchor="w", padx=px(14),
                                               pady=(px(10), px(2)))


class MainWindow:
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root)
        self.win.title(paths.APP_NAME)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            self.win.iconbitmap(paths.asset_path("app.ico"))
        except Exception:
            pass
        self._build()
        center(self.win, WIDTH, HEIGHT)
        self.refresh()

    # ------------------------------------------------------------ 构建
    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except Exception:
            return False

    def show(self):
        if not self.alive():
            return
        self.win.deiconify()
        self.win.lift()
        self.win.focus_force()
        self.refresh()

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    def _build(self):
        # ---- 顶部横幅
        head = tk.Frame(self.win, bg=ACCENT, height=px(88))
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="classDesktopManager", bg=ACCENT, fg="#FFFFFF",
                 font=_font(16, True)).pack(anchor="w", padx=px(18),
                                            pady=(px(14), 0))
        self.lbl_status = tk.Label(head, text="", bg=ACCENT, fg="#D6E4F5",
                                   font=_font(9), anchor="w")
        self.lbl_status.pack(anchor="w", padx=px(18), pady=(px(2), 0))

        wrap = tk.Frame(self.win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=px(14), pady=px(12))

        # ---- 状态卡
        card = Card(wrap)
        card.pack(fill="x")
        self._row(card, "监视目录", "lbl_desktop")
        self._row(card, "科目文件夹", "lbl_subjects")
        self._row(card, "检测方式", "lbl_mode")
        self._row(card, "关注类型", "lbl_kinds")
        tk.Frame(card, bg=CARD, height=px(8)).pack()

        # ---- 操作按钮
        btns = tk.Frame(wrap, bg=BG)
        btns.pack(fill="x", pady=(px(12), 0))
        for i in range(4):
            btns.columnconfigure(i, weight=1, uniform="b")
        self.btn_check = FlatButton(btns, "立即检测", self._check_now, "primary")
        self.btn_check.grid(row=0, column=0, sticky="ew", padx=(0, px(4)))
        self.btn_pause = FlatButton(btns, "暂停提醒", self._toggle_pause)
        self.btn_pause.grid(row=0, column=1, sticky="ew", padx=px(4))
        self.btn_desktop = FlatButton(btns, "打开桌面", self.app.open_desktop)
        self.btn_desktop.grid(row=0, column=2, sticky="ew", padx=px(4))
        self.btn_settings = FlatButton(btns, "设置", self.app.open_settings)
        self.btn_settings.grid(row=0, column=3, sticky="ew", padx=(px(4), 0))

        # ---- 科目列表
        card2 = Card(wrap, "科目文件夹（双击可直接打开）")
        card2.pack(fill="both", expand=True, pady=(px(12), 0))
        holder = tk.Frame(card2, bg=CARD)
        holder.pack(fill="both", expand=True, padx=px(14), pady=(px(4), px(12)))
        self.list_subjects = tk.Listbox(
            holder, bg=SOFT, fg=TEXT, font=_font(10), relief="flat",
            bd=0, highlightthickness=0, activestyle="none",
            selectbackground="#DCE9F7", selectforeground=TEXT, height=6)
        sb = tk.Scrollbar(holder, command=self.list_subjects.yview,
                          relief="flat", bd=0, width=px(12))
        self.list_subjects.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.list_subjects.pack(side="left", fill="both", expand=True)
        self.list_subjects.bind("<Double-Button-1>", self._open_selected)

        # ---- 最近记录
        card3 = Card(wrap, "最近的归档记录")
        card3.pack(fill="both", expand=True, pady=(px(12), 0))
        self.txt_log = tk.Text(
            card3, bg=SOFT, fg=TEXT, font=_font(9), relief="flat",
            bd=0, highlightthickness=0, height=6, wrap="none",
            state="disabled", padx=px(8), pady=px(6))
        self.txt_log.pack(fill="both", expand=True, padx=px(14),
                          pady=(px(4), px(12)))

        # ---- 底栏
        foot = tk.Frame(self.win, bg=BG)
        foot.pack(fill="x", padx=px(14), pady=(0, px(12)))
        tk.Label(foot, text="v%s · 单击托盘图标可打开本窗口或退出"
                 % paths.APP_VERSION, bg=BG, fg=MUTED,
                 font=_font(8)).pack(side="left")
        FlatButton(foot, "退出软件", self.app.shutdown,
                   "danger").pack(side="right")
        FlatButton(foot, "关于", self._about).pack(side="right", padx=(0, px(8)))

    def _row(self, card, label, attr):
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=px(4))
        tk.Label(row, text=label, bg=CARD, fg=MUTED, font=_font(9),
                 width=8, anchor="w").pack(side="left")
        lbl = tk.Label(row, text="-", bg=CARD, fg=TEXT, font=_font(9),
                       anchor="w", justify="left",
                       wraplength=WIDTH - px(150))
        lbl.pack(side="left", fill="x", expand=True)
        setattr(self, attr, lbl)

    # ------------------------------------------------------------ 刷新
    def refresh(self):
        if not self.alive():
            return
        app = self.app
        cfg = app.cfg
        paused = bool(cfg.get("paused"))
        self.lbl_status.configure(
            text=("已暂停提醒 · 单击「继续提醒」恢复" if paused
                  else "正在后台监视桌面 · 新文件会弹出人物提示"))
        self.lbl_desktop.configure(
            text=short_path(cfg.get("desktop_path") or "-", 34))
        names = config.subject_names(cfg)
        self.lbl_subjects.configure(text="%d 个 · %s" % (
            len(names), "、".join(names[:6]) + ("…" if len(names) > 6 else "")))
        mode = cfg.get("detect_mode", "smart")
        self.lbl_mode.configure(text={
            "smart": "智能（U 盘来源，或关注类型的新文件）",
            "usb": "仅 U 盘来源",
            "all": "桌面新增任何文件",
            "off": "关闭提醒",
        }.get(mode, mode))
        kinds = config.auto_kinds(cfg)
        if kinds:
            text = "、".join(config.kind_label(k) for k in kinds)
            if cfg.get("ask_unknown", True):
                text += "（认不出科目时会问您放哪儿）"
        else:
            text = "未选择（只提醒能认出科目的文件）"
        self.lbl_kinds.configure(text=text)
        self.btn_pause.configure(text="继续提醒" if paused else "暂停提醒",
                                 bg=OK if paused else "#FFFFFF",
                                 fg="#FFFFFF" if paused else TEXT,
                                 activebackground="#276749" if paused else "#E8EEF6")

        self.list_subjects.delete(0, "end")
        desktop = cfg.get("desktop_path") or ""
        for n in names:
            exists = os.path.isdir(os.path.join(desktop, n))
            self.list_subjects.insert(
                "end", "  %s   %s" % ("[已有]" if exists else "[待建]", n))

        hist = config.load_history()[-14:]
        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        if not hist:
            self.txt_log.insert("end", "还没有归档记录。\n")
        else:
            for rec in reversed(hist):
                self.txt_log.insert("end", "· %s  →  %s\n"
                                    % (config.short_name(rec.get("name", ""), 30),
                                       rec.get("subject", "")))
        self.txt_log.configure(state="disabled")

    # ------------------------------------------------------------ 交互
    def _toggle_pause(self):
        self.app.toggle_pause()

    def _check_now(self):
        self.app._spawn(self.app.check_now)

    def _open_selected(self, _evt=None):
        sel = self.list_subjects.curselection()
        if not sel:
            return
        raw = self.list_subjects.get(sel[0])
        name = raw.split("]", 1)[-1].strip()
        if name:
            self.app.open_subject_folder(name)

    def _about(self):
        messagebox.showinfo(
            paths.APP_NAME,
            "版本 %s\n\n把 U 盘里的文件复制到桌面时，我会用人物对话气泡提醒您\n"
            "把它放进对应的科目文件夹，还可以一键帮您移过去。\n\n"
            "配置文件：%s" % (paths.APP_VERSION, paths.appdata_dir()),
            parent=self.win)

    def on_close(self):
        if self.app.cfg.get("close_to_tray", True):
            self.hide()
        else:
            self.app.shutdown()
