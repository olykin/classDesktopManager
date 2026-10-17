# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""气泡绘制：把人物形象 + 对话气泡渲染成一张带透明通道的位图。

绘制策略：图形部分在放大的画布上超采样后缩小（边缘平滑），文字在最终尺寸
上绘制（保证清晰）。渲染结果交给分层窗口逐像素合成到桌面上。

“高分辨率优化”：``_ss_for(s)`` 保证图形的采样倍率在任何缩放比下都不低于
2 倍，小屏（s<2）时提到 3 倍，避免圆角/描边在高 PPI 屏上出现台阶。
"""
from __future__ import annotations

import os
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from . import paths


def _ss_for(s):
    """按缩放比选择超采样倍率。"""
    return 3 if float(s) < 2.0 else 2


SS = 2  # 默认超采样倍数（实际由 _ss_for 决定）

_FONT_CACHE = {}
_CHAR_CACHE = {}

TITLE_SIZE = 17
BODY_SIZE = 14
HINT_SIZE = 11
BTN_SIZE = 14
CLOSE_SIZE = 15

MAX_TEXT_W = 372
BTN_ROW_MAX_W = 480      # 按钮整排的最大宽度（比正文上限宽，避免按钮被折行）
CHAR_BOX = 208          # 人物显示高度（逻辑像素）
GAP = 4                 # 人物与气泡的间距
PAD = 16                # 位图四周留白（阴影需要空间）
BUBBLE_PAD_X = 20
BUBBLE_PAD_Y = 16
BUBBLE_RADIUS = 18
TAIL_W = 16
TAIL_H = 22
BTN_H = 44              # 触摸目标高度（逻辑像素，>=44 才够手指点）
BTN_GAP = 10
BTN_PAD_X = 20


# ------------------------------------------------------------------ 字体
def _font_candidates(bold):
    win = os.environ.get("WINDIR", r"C:\Windows")
    fonts = os.path.join(win, "Fonts")
    if bold:
        names = ["msyhbd.ttc", "msyh.ttc", "simhei.ttf", "Deng.ttf",
                 "simsun.ttc", "segoeuib.ttf", "arialbd.ttf"]
    else:
        names = ["msyh.ttc", "msyhl.ttc", "simhei.ttf", "Deng.ttf",
                 "simsun.ttc", "segoeui.ttf", "arial.ttf"]
    for n in names:
        p = os.path.join(fonts, n)
        if os.path.isfile(p):
            yield p


def load_font(size, bold=False):
    key = (int(size), bool(bold))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    font = None
    for p in _font_candidates(bold):
        try:
            font = ImageFont.truetype(p, int(size))
            break
        except Exception:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(int(size))
        except Exception:
            font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font


def load_character(path, box):
    """加载并按 box 高度等比缩放人物（带缓存）。

    path 为空或文件读不出来时，退回一个等尺寸的透明占位图，
    保证气泡本身仍然能正常显示（不因为人物素材缺失而整个弹不出来）。
    """
    box = max(1, int(box))
    key = (path, box)
    try:
        mtime = os.path.getmtime(path) if path else 0
    except OSError:
        mtime = 0
    im = None
    if path:
        hit = _CHAR_CACHE.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
        try:
            im = Image.open(path).convert("RGBA")
        except Exception:
            im = None
    if im is None:
        im = Image.new("RGBA", (box, box), (0, 0, 0, 0))
        return im
    w, h = im.size
    scale = float(box) / float(h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    im = im.resize((nw, nh), Image.LANCZOS)
    _CHAR_CACHE[key] = (mtime, im)
    return im


def _measure(draw, text, font):
    if not text:
        return 0
    try:
        return int(draw.textlength(text, font=font))
    except Exception:
        return int(font.getlength(text))


def wrap_text(text, font, max_w, draw):
    """中英文混排换行。"""
    out = []
    for para in str(text).split("\n"):
        if not para:
            out.append("")
            continue
        line = ""
        for ch in para:
            trial = line + ch
            if _measure(draw, trial, font) <= max_w or not line:
                line = trial
                continue
            brk = -1
            for i in range(len(line) - 1, max(-1, len(line) - 14), -1):
                if line[i] in " \t,.;:!?)]}、，。；：！？）》」』":
                    brk = i + 1
                    break
            if brk > 0:
                out.append(line[:brk].rstrip())
                line = line[brk:].lstrip() + ch
            else:
                out.append(line)
                line = ch
        out.append(line)
    return out


# ------------------------------------------------------------------ 布局
def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


class Layout:
    def __init__(self):
        self.width = 0
        self.height = 0
        self.char_pos = (0, 0)
        self.char_size = (0, 0)
        self.bubble = (0, 0, 0, 0)     # x0,y0,x1,y1
        self.tail_y = 0
        self.flip = False              # True = 人物在右、气泡在左
        self.buttons = []              # [(x0,y0,x1,y1,id,kind)]
        self.close_rect = (0, 0, 0, 0)
        self.title = ""
        self.accent = (0, 0, 0, 255)
        self.char_image = None
        self._scale = 1.0
        self._f_title = None
        self._f_body = None
        self._f_hint = None
        self._f_btn = None
        self._title_lines = []
        self._body_lines = []
        self._hint_lines = []
        self._btn_rows = []
        self._btn_sizes = []
        self._btn_labels = {}


def build_layout(spec, scale=1.0):
    """根据 spec 计算布局。spec 见 bubble.make_spec()。"""
    s = float(scale)
    flip = bool(spec.get("flip"))
    accent = _hex(spec.get("accent", "#2F855A"))
    title = spec.get("title", "") or ""
    body = [b for b in (spec.get("body") or [])]
    hint = spec.get("hint", "") or ""
    buttons = list(spec.get("buttons") or [])

    # 度量用的临时画布
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    f_title = load_font(round(TITLE_SIZE * s), bold=True)
    f_body = load_font(round(BODY_SIZE * s))
    f_hint = load_font(round(HINT_SIZE * s))
    f_btn = load_font(round(BTN_SIZE * s), bold=True)

    max_text = MAX_TEXT_W * s

    title_lines = wrap_text(title, f_title, max_text, probe) if title else []
    body_lines = []
    for b in body:
        for ln in wrap_text(b, f_body, max_text, probe):
            body_lines.append(ln)
    if title_lines and body_lines and body_lines[0] == "":
        body_lines.pop(0)
    hint_lines = wrap_text(hint, f_hint, max_text, probe) if hint else []

    # 按钮宽度
    btn_sizes = []
    for b in buttons:
        tw = _measure(probe, b.get("text", ""), f_btn)
        btn_sizes.append((int(tw + 2 * BTN_PAD_X * s), int(BTN_H * s)))

    # 文本区自然宽度
    natural = 0
    for ln in title_lines:
        natural = max(natural, _measure(probe, ln, f_title))
    for ln in body_lines:
        natural = max(natural, _measure(probe, ln, f_body))
    for ln in hint_lines:
        natural = max(natural, _measure(probe, ln, f_hint))
    # 单行按钮不应成为宽度瓶颈（放不下就换行）
    min_w = 300 * s
    max_w = max_text + 2 * BUBBLE_PAD_X * s
    text_w = max(min_w, min(natural + 2 * BUBBLE_PAD_X * s, max_w))
    pad_x = 2 * BUBBLE_PAD_X * s
    gap = BTN_GAP * s
    one_row = (sum(w for w, _ in btn_sizes) + gap * (len(btn_sizes) - 1)) \
        if btn_sizes else 0
    row_max_w = max(max_w, BTN_ROW_MAX_W * s)
    if btn_sizes and one_row + pad_x <= row_max_w:
        btn_rows = [([(i, b) for i, b in enumerate(buttons)], one_row)]
        text_w = max(text_w, min(one_row + pad_x, row_max_w))
    else:
        btn_rows = _layout_buttons(btn_sizes, buttons, text_w - pad_x, gap)
    for row, _ in btn_rows:
        need = sum(btn_sizes[i][0] for i, _ in row) + gap * (len(row) - 1)
        text_w = max(text_w, need + pad_x)
    bubble_w = int(round(text_w))

    # 气泡高度
    lh_title = int(TITLE_SIZE * s * 1.42)
    lh_body = int(BODY_SIZE * s * 1.62)
    lh_hint = int(HINT_SIZE * s * 1.6)
    content_h = 0
    if title_lines:
        content_h += lh_title * len(title_lines) + int(6 * s)
    if body_lines:
        content_h += lh_body * len(body_lines)
    if hint_lines:
        content_h += int(6 * s) + lh_hint * len(hint_lines)
    btn_block = len(btn_rows) * int(BTN_H * s) + (len(btn_rows) - 1) * int(BTN_GAP * s) \
        if btn_rows else 0
    if btn_block:
        content_h += int(12 * s) + btn_block
    bubble_h = int(content_h + 2 * BUBBLE_PAD_Y * s)
    bubble_h = max(bubble_h, int(120 * s))

    char_box = int(CHAR_BOX * s)
    char_img = load_character(spec.get("character_path"), char_box)
    cw, ch = char_img.size

    total_w = int(PAD * s * 2 + cw + GAP * s + bubble_w)
    total_h = int(PAD * s * 2 + max(ch, bubble_h))

    lay = Layout()
    lay.width, lay.height = total_w, total_h
    lay.accent = accent
    lay.title = title
    lay.char_image = char_img
    lay.flip = flip

    char_y = int(PAD * s)
    if flip:
        bubble_x = int(PAD * s)
        char_x = total_w - int(PAD * s) - cw
    else:
        char_x = int(PAD * s)
        bubble_x = int(PAD * s) + cw + int(GAP * s)
    bubble_y = int(PAD * s) + max(0, int((ch - bubble_h) * 0.22))
    if bubble_y + bubble_h > total_h - int(PAD * s):
        bubble_y = total_h - int(PAD * s) - bubble_h

    lay.char_pos = (char_x, char_y)
    lay.char_size = (cw, ch)
    lay.bubble = (bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h)
    lay.tail_y = bubble_y + int(56 * s) if not flip else bubble_y + int(56 * s)
    lay.flip = flip
    lay._f_title = f_title
    lay._f_body = f_body
    lay._f_hint = f_hint
    lay._f_btn = f_btn
    lay._title_lines = title_lines
    lay._body_lines = body_lines
    lay._hint_lines = hint_lines
    lay._btn_rows = btn_rows
    lay._btn_sizes = btn_sizes
    lay._btn_labels = {b.get("id", ""): b.get("text", "") for b in buttons}
    lay._scale = s

    # 按钮矩形在这里就算好，供命中测试与绘制共用
    # （以前只在 render() 里算，导致 build_layout 的返回值少了按钮信息）
    btn_area_x1 = (bubble_x + bubble_w) - int(BUBBLE_PAD_X * s)
    row_h = int(BTN_H * s)
    btn_gap_px = int(BTN_GAP * s)
    by = (bubble_y + bubble_h) - int(BUBBLE_PAD_Y * s) \
        - len(btn_rows) * row_h - max(0, len(btn_rows) - 1) * btn_gap_px
    lay.buttons = []
    for row, row_w in btn_rows:
        bx = btn_area_x1 - row_w
        for idx, b in row:
            bw = btn_sizes[idx][0]
            lay.buttons.append((bx, by, bx + bw, by + row_h,
                                b.get("id", ""), b.get("kind", "ghost")))
            bx += bw + btn_gap_px
        by += row_h + btn_gap_px
    return lay


def _layout_buttons(btn_sizes, buttons, max_row_w, gap=None):
    """把按钮排成若干行，返回 [([(索引, button)], row_width), ...]"""
    if gap is None:
        gap = BTN_GAP
    rows = []
    cur = []
    cur_w = 0
    for i, b in enumerate(buttons):
        bw = btn_sizes[i][0]
        add = bw if not cur else bw + gap
        if cur and cur_w + add > max_row_w + 40:
            rows.append((cur, cur_w))
            cur = [(i, b)]
            cur_w = bw
        else:
            cur.append((i, b))
            cur_w += add
    if cur:
        rows.append((cur, cur_w))
    return rows


# ------------------------------------------------------------------ 绘制
def _rrect(d, box, r, fill=None, outline=None, width=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def render(lay, hover_id=None, pressed_id=None):
    """渲染成 RGBA 图（1 倍尺寸）。"""
    s = lay._scale
    W, H = lay.width, lay.height
    SS = _ss_for(s)
    img = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = SS  # 超采样系数（此处直接用像素坐标乘 SS）

    def R(x0, y0, x1, y1):
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    bx0, by0, bx1, by1 = lay.bubble
    rad = int(BUBBLE_RADIUS * s)
    accent = lay.accent
    accent_dark = tuple(max(0, int(c * 0.86)) for c in accent[:3]) + (255,)

    # ---- 气泡阴影
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sh)
    _rrect(ds, R(bx0, by0 + int(3 * s), bx1, by1 + int(6 * s)), rad * k,
           fill=(15, 23, 42, 78))
    sh = sh.filter(ImageFilter.GaussianBlur(7 * s * k))
    img.alpha_composite(sh)
    d = ImageDraw.Draw(img)

    # ---- 尾巴（先画，让气泡本体压住接缝）
    ty = lay.tail_y
    tw = int(TAIL_W * s)
    th = int(TAIL_H * s)
    if lay.flip:
        pts = [(bx1, ty - th // 2), (bx1, ty + th // 2), (bx1 + tw, ty)]
    else:
        pts = [(bx0, ty - th // 2), (bx0, ty + th // 2), (bx0 - tw, ty)]
    d.polygon([(p[0] * k, p[1] * k) for p in pts], fill=(255, 255, 255, 255))

    # ---- 气泡本体
    border = (226, 232, 240, 255)
    _rrect(d, R(bx0, by0, bx1, by1), rad * k, fill=(255, 255, 255, 255),
           outline=border, width=max(1, int(1.3 * s * k)))
    # 顶部强调色细条（嵌在圆角内）
    strip_h = int(4 * s)
    d.rounded_rectangle([(bx0 + rad) * k, by0 * k,
                         (bx1 - rad) * k, (by0 + strip_h) * k],
                        radius=int(strip_h * 0.5 * k), fill=accent)

    # ---- 按钮（矩形已由 build_layout 算好，这里只画）
    area_x0 = bx0 + int(BUBBLE_PAD_X * s)
    area_x1 = bx1 - int(BUBBLE_PAD_X * s)
    for (rect0, rect1, rect2, rect3, bid, kind) in lay.buttons:
        rect = (rect0, rect1, rect2, rect3)
        pressed = pressed_id == bid
        hovered = hover_id == bid
        br = int(10 * s)
        if kind == "primary":
            fill = accent_dark if (pressed or hovered) else accent
            _rrect(d, R(rect[0], rect[1], rect[2], rect[3]), br * k, fill=fill)
        else:
            if pressed:
                fill = (226, 232, 240, 255)
            elif hovered:
                fill = (238, 242, 247, 255)
            else:
                fill = (244, 246, 250, 255)
            _rrect(d, R(rect[0], rect[1], rect[2], rect[3]), br * k,
                   fill=fill, outline=border, width=max(1, int(1.2 * s * k)))

    # ---- 关闭按钮（视觉 26 逻辑像素；命中区由 bubble.py 放大到 44）
    cs = int(26 * s)
    close_rect = (bx1 - int(BUBBLE_PAD_X * s * 0.6) - cs,
                  by0 + int(10 * s),
                  bx1 - int(BUBBLE_PAD_X * s * 0.6),
                  by0 + int(10 * s) + cs)
    lay.close_rect = close_rect
    if hover_id == "__close" or pressed_id == "__close":
        d.ellipse([close_rect[0] * k, close_rect[1] * k,
                   close_rect[2] * k, close_rect[3] * k],
                  fill=(241, 245, 249, 255))
    cx = (close_rect[0] + close_rect[2]) / 2.0
    cy = (close_rect[1] + close_rect[3]) / 2.0
    rr = int(5 * s)
    wdt = max(1, int(1.6 * s * k))
    d.line([(cx - rr) * k, (cy - rr) * k, (cx + rr) * k, (cy + rr) * k],
           fill=(148, 163, 184, 255), width=wdt)
    d.line([(cx - rr) * k, (cy + rr) * k, (cx + rr) * k, (cy - rr) * k],
           fill=(148, 163, 184, 255), width=wdt)

    # ---- 缩回 1 倍，贴人物
    img = img.resize((W, H), Image.LANCZOS)
    ci = lay.char_image
    if ci is not None:
        img.alpha_composite(ci, lay.char_pos)
    d = ImageDraw.Draw(img)

    # ---- 文字（1 倍尺寸绘制，保证清晰）
    tx = area_x0
    tx1 = area_x1 - int(26 * s)
    cy_cursor = by0 + int(BUBBLE_PAD_Y * s) + int(4 * s)
    lh_title = int(TITLE_SIZE * s * 1.42)
    lh_body = int(BODY_SIZE * s * 1.62)
    lh_hint = int(HINT_SIZE * s * 1.6)

    for ln in lay._title_lines:
        d.text((tx, cy_cursor), ln, font=lay._f_title, fill=accent)
        cy_cursor += lh_title
    if lay._title_lines and lay._body_lines:
        cy_cursor += int(6 * s)
    for ln in lay._body_lines:
        d.text((tx, cy_cursor), ln, font=lay._f_body, fill=(51, 65, 85, 255))
        cy_cursor += lh_body
    if lay._hint_lines:
        cy_cursor += int(6 * s)
        for ln in lay._hint_lines:
            d.text((tx, cy_cursor), ln, font=lay._f_hint, fill=(148, 163, 184, 255))
            cy_cursor += lh_hint

    for (x0, y0, x1, y1, bid, kind) in lay.buttons:
        label = lay._btn_labels.get(bid, "")
        col = (255, 255, 255, 255) if kind == "primary" else (71, 85, 105, 255)
        tw = _measure(d, label, lay._f_btn)
        d.text(((x0 + x1 - tw) / 2.0, (y0 + y1) / 2.0), label,
               font=lay._f_btn, fill=col, anchor="lm")

    return img
