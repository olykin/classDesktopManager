# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""生成应用图标 app.ico（文件夹 + 提醒气泡）。"""
from __future__ import annotations

import os

from PIL import Image, ImageDraw

S = 1024          # 绘制尺寸
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                   "src", "dsr", "assets", "app.ico")
PREVIEW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "_scratch", "app_icon.png")

BLUE_TOP = (59, 130, 246)
BLUE_BOT = (29, 78, 216)
FOLDER = (255, 255, 255)


def draw_base():
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(S * 0.22)
    # 竖向渐变
    grad = Image.new("RGBA", (1, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / float(S - 1)
        gd.point((0, y), fill=tuple(
            int(BLUE_TOP[i] + (BLUE_BOT[i] - BLUE_TOP[i]) * t)
            for i in range(3)) + (255,))
    grad = grad.resize((S, S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    return img, d


def draw_folder(d):
    x0 = int(S * 0.17)
    x1 = int(S * 0.83)
    y0 = int(S * 0.31)
    y1 = int(S * 0.79)
    tab_h = int(S * 0.075)
    tab_w = int(S * 0.30)
    r = int(S * 0.045)
    # 标签页（上方小凸块）
    d.rounded_rectangle([x0, y0 - tab_h, x0 + tab_w, y0 + tab_h],
                        radius=r, fill=FOLDER)
    # 主体
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=FOLDER)
    # 内部横线，增加层次
    d.rounded_rectangle([x0 + int(S * 0.06), y0 + int(S * 0.09),
                         x1 - int(S * 0.06), y0 + int(S * 0.115)],
                        radius=int(S * 0.014),
                        fill=(191, 219, 254, 255))


def draw_badge(d):
    cx = int(S * 0.735)
    cy = int(S * 0.735)
    rr = int(S * 0.165)
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(245, 158, 11, 255),
              outline=(255, 255, 255, 255), width=int(S * 0.022))
    bar_w = int(S * 0.046)
    top = cy - int(S * 0.088)
    bot = cy + int(S * 0.030)
    d.rounded_rectangle([cx - bar_w // 2, top, cx + bar_w // 2, bot],
                        radius=bar_w // 2, fill=(255, 255, 255, 255))
    dot_r = int(S * 0.028)
    d.ellipse([cx - dot_r, cy + int(S * 0.062) - dot_r,
               cx + dot_r, cy + int(S * 0.062) + dot_r],
              fill=(255, 255, 255, 255))


def main():
    img, d = draw_base()
    draw_folder(d)
    draw_badge(d)
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(PREVIEW)), exist_ok=True)
    sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]
    img.save(OUT, format="ICO",
             sizes=[(s, s) for s in sizes])
    img.resize((256, 256), Image.LANCZOS).save(PREVIEW)
    print("saved", os.path.abspath(OUT))
    print("saved", os.path.abspath(PREVIEW))


if __name__ == "__main__":
    main()
