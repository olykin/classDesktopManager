# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""「这个文件放哪儿呢？」——认不出科目时，让老师亲自选一个文件夹。"""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import simpledialog

from . import config, paths, winapi
from .uishared import (BG, BORDER, CARD, DANGER, MUTED, OK, SOFT, TEXT, WARN,
                       center as _center, font as _font, px, short_path)

WA = winapi.work_area()
W = min(px(580), int(WA[2] * 0.92))
H = min(px(620), int((WA[3] - WA[1]) * 0.92))


class FlatButton(tk.Button):
    def __init__(self, master, text, command, kind="ghost", **kw):
        colors = {
            "primary": (OK, "#FFFFFF", "#276749"),
            "ghost": ("#FFFFFF", TEXT, "#E8EEF6"),
            "warn": (WARN, "#FFFFFF", "#96601A"),
            "danger": ("#FFFFFF", DANGER, "#FBEAEA"),
        }[kind]
        bg, fg, active = colors
        super().__init__(master, text=text, command=command, bg=bg, fg=fg,
                         activebackground=active, activeforeground=fg,
                         relief="flat", bd=0, highlightthickness=1,
                         highlightbackground=BORDER if kind == "ghost" else bg,
                         highlightcolor=BORDER if kind == "ghost" else bg,
                         font=_font(10, kind != "ghost"), cursor="hand2",
                         padx=px(14), pady=px(7), **kw)


class FolderPicker:
    """选择归档目标文件夹的小窗口。

    用法：``FolderPicker(app, path, size, origin, kind, on_done)``，
    ``on_done(subject)`` 在老师确定后回调（取消时传空串）。
    """

    def __init__(self, app, path, size=0, origin="", kind="", on_done=None):
        self.app = app
        self.on_done = on_done
        self.path = path
        self.remember = None
        self._thumb = None

        self.win = tk.Toplevel(app.root)
        self.win.title("选择归档文件夹 - %s" % paths.APP_NAME)
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        try:
            self.win.iconbitmap(paths.asset_path("app.ico"))
        except Exception:
            pass
        self._build()
        _center(self.win, W, H, bias=4)
        self.set_file(path, size, origin, kind, on_done)
        self.win.bind("<MouseWheel>", lambda e: self.scroll.on_wheel(e))
        self.win.bind("<Escape>", lambda e: self._cancel())
        self.win.bind("<Return>", lambda e: self._confirm())

    # ------------------------------------------------------------ 基础
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

    def hide(self):
        try:
            self.win.withdraw()
        except Exception:
            pass

    # ------------------------------------------------------------ 构建
    def _build(self):
        head = tk.Frame(self.win, bg=WARN, height=px(70))
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="这个文件放在哪儿呢？", bg=WARN, fg="#FFFFFF",
                 font=_font(14, True)).pack(anchor="w", padx=px(18),
                                            pady=(px(10), 0))
        tk.Label(head, text="选好文件夹后我会把文件移过去，并记住这次选择",
                 bg=WARN, fg="#FDF0D5", font=_font(9)).pack(anchor="w",
                                                             padx=px(18))

        wrap = tk.Frame(self.win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=px(14), pady=px(10))

        # ---- 文件信息卡
        info = tk.Frame(wrap, bg=CARD, highlightthickness=1,
                        highlightbackground=BORDER)
        info.pack(fill="x")
        row = tk.Frame(info, bg=CARD)
        row.pack(fill="x", padx=px(14), pady=(px(10), px(4)))
        self.lbl_thumb = tk.Label(row, bg=SOFT, fg=MUTED, font=_font(8),
                                  width=10, height=5)
        self.lbl_thumb.pack(side="left", padx=(0, px(12)))
        col = tk.Frame(row, bg=CARD)
        col.pack(side="left", fill="both", expand=True)
        self.lbl_name = tk.Label(col, text="-", bg=CARD, fg=TEXT,
                                 font=_font(11, True), anchor="w",
                                 justify="left", wraplength=W - px(190))
        self.lbl_name.pack(anchor="w", fill="x")
        self.lbl_meta = tk.Label(col, text="-", bg=CARD, fg=MUTED,
                                 font=_font(9), anchor="w", justify="left",
                                 wraplength=W - px(190))
        self.lbl_meta.pack(anchor="w", fill="x", pady=(px(2), 0))
        tk.Frame(info, bg=CARD, height=px(6)).pack()

        # ---- 文件夹列表
        card = tk.Frame(wrap, bg=CARD, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="both", expand=True, pady=(px(10), 0))
        tk.Label(card, text="放到哪个文件夹（桌面下）", bg=CARD, fg=MUTED,
                 font=_font(9, True)).pack(anchor="w", padx=px(14),
                                           pady=(px(10), px(4)))
        holder = tk.Frame(card, bg=CARD)
        holder.pack(fill="both", expand=True, padx=px(14), pady=(0, px(6)))
        self.lst = tk.Listbox(holder, bg=SOFT, fg=TEXT, font=_font(10),
                              relief="flat", bd=0, highlightthickness=0,
                              activestyle="none", exportselection=False,
                              selectbackground="#DCE9F7",
                              selectforeground=TEXT)
        sb = tk.Scrollbar(holder, command=self.lst.yview, relief="flat",
                          bd=0, width=px(12))
        self.lst.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.lst.pack(side="left", fill="both", expand=True)
        self.lst.bind("<<ListboxSelect>>", lambda e: self._on_select())
        self.lst.bind("<Double-Button-1>", lambda e: self._confirm())

        brow = tk.Frame(card, bg=CARD)
        brow.pack(fill="x", padx=px(14), pady=(px(2), px(8)))
        FlatButton(brow, "新建文件夹…", self._new_folder).pack(side="left")
        FlatButton(brow, "打开桌面", self._open_desktop).pack(
            side="left", padx=px(6))
        FlatButton(brow, "刷新列表", self._reload).pack(side="left")

        # ---- 记住选择
        self.v_remember = tk.BooleanVar(value=False)
        self.chk = tk.Checkbutton(
            wrap, text="记住：以后相同类型的文件都放这里",
            variable=self.v_remember, bg=BG, fg=TEXT, font=_font(9),
            anchor="w", activebackground=BG, selectcolor="#FFFFFF",
            highlightthickness=0, cursor="hand2")
        self.chk.pack(anchor="w", pady=(px(8), 0))

        # ---- 底部
        foot = tk.Frame(self.win, bg=BG)
        foot.pack(fill="x", padx=px(14), pady=(0, px(12)))
        FlatButton(foot, "移入这个文件夹", self._confirm,
                   "primary").pack(side="right")
        FlatButton(foot, "取消", self._cancel).pack(side="right", padx=px(8))

        self._reload()

    # ------------------------------------------------------------ 数据
    def _candidates(self):
        """返回候选文件夹：既有科目 + 桌面上真实存在的其它子文件夹。"""
        desktop = self.app.desktop
        names = list(config.subject_names(self.app.cfg))
        try:
            for entry in sorted(os.listdir(desktop)):
                full = os.path.join(desktop, entry)
                if not os.path.isdir(full):
                    continue
                if entry.startswith(".") or entry.startswith("$"):
                    continue
                if entry not in names:
                    names.append(entry)
        except Exception:
            pass
        return names

    def _reload(self):
        self._names = self._candidates()
        desktop = self.app.desktop
        self.lst.delete(0, "end")
        for n in self._names:
            exists = os.path.isdir(os.path.join(desktop, n))
            self.lst.insert("end", "  %s   %s"
                            % ("[已有]" if exists else "[待建]", n))
        if self._names:
            self.lst.selection_clear(0, "end")
            self.lst.selection_set(0)
            self.lst.see(0)
        self._on_select()

    def _selected_name(self):
        sel = self.lst.curselection()
        if not sel or sel[0] >= len(getattr(self, "_names", [])):
            return ""
        return self._names[sel[0]]

    def _on_select(self):
        name = self._selected_name()
        if name:
            self.chk.configure(
                text="记住：以后「%s」类型的文件都放进「%s」"
                     % (config.file_ext(self.path) or "这种", name))
            self.chk.configure(state="normal")
        else:
            self.chk.configure(state="disabled")

    def _new_folder(self):
        name = simpledialog.askstring("新建文件夹", "新文件夹的名称：",
                                      parent=self.win)
        if not name or not name.strip():
            return
        name = name.strip()
        try:
            os.makedirs(os.path.join(self.app.desktop, name), exist_ok=True)
        except Exception:
            pass
        # 顺手加进科目列表，下次就能自动识别了
        if name not in config.subject_names(self.app.cfg):
            self.app.cfg.setdefault("subjects", []).append(
                config.normalize_subject(name))
            config.save(self.app.cfg)
            self.app.refresh_main()
        self._reload()
        if name in getattr(self, "_names", []):
            idx = self._names.index(name)
            self.lst.selection_clear(0, "end")
            self.lst.selection_set(idx)
            self.lst.see(idx)
            self._on_select()

    def _open_desktop(self):
        self.app.open_desktop()

    # ------------------------------------------------------------ 换文件
    def set_file(self, path, size=0, origin="", kind="", on_done=None):
        self.path = path
        self.origin = origin
        self.on_done = on_done
        name = os.path.basename(path)
        self.win.title("选择归档文件夹 - %s" % config.short_name(name, 30))
        self.lbl_name.configure(text="《%s》" % config.short_name(name, 40))
        bits = []
        if size:
            bits.append("大小 %s" % config.human_size(size))
        if origin:
            bits.append("来自 %s" % origin)
        if kind:
            bits.append(config.kind_label(kind))
        bits.append(short_path(os.path.dirname(path), 30))
        self.lbl_meta.configure(text=" · ".join(bits))
        if not getattr(self, "_names", None):
            self._reload()
        self.v_remember.set(False)
        self._load_thumb(path, kind)
        self._on_select()

    def _load_thumb(self, path, kind):
        self.lbl_thumb.configure(image="", text="(无预览)", width=10, height=5)
        self._thumb = None
        try:
            from PIL import Image, ImageTk
            if kind == "image" or config.file_kind(os.path.basename(path)) \
                    == "image":
                im = Image.open(path).convert("RGB")
                im.thumbnail((px(104), px(78)), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
                self._thumb = photo
                self.lbl_thumb.configure(image=photo, text="", width=0,
                                         height=0)
        except Exception:
            pass

    # ------------------------------------------------------------ 收尾
    def _confirm(self):
        name = self._selected_name()
        if not name:
            return
        remember = bool(self.v_remember.get())
        path = self.path
        origin = getattr(self, "origin", "")
        self.hide()
        self.app.place_file(path, name, origin, remember_ext=remember)
        cb = self.on_done
        self.on_done = None
        if cb:
            cb(name)

    def _cancel(self):
        self.hide()
        cb = self.on_done
        self.on_done = None
        if cb:
            cb("")
