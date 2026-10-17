# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""生成提醒人物形象（透明背景 PNG）。

所有形象均以 4 倍超采样绘制后缩放，得到平滑边缘，并以透明背景输出，
供分层窗口（UpdateLayeredWindow）直接合成到桌面上。

输出目录：src/dsr/assets/characters/
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFilter

S = 6          # 超采样倍数（相对逻辑画布）
W = H = 1024   # 导出尺寸（高分辨率屏下气泡里的人物更大，需要更细的素材）
LW = LH = 512  # 逻辑画布（下面所有绘图坐标都在这个尺度上书写）
CW, CH = LW * S, LH * S
K = W / float(LW)   # 逻辑坐标 -> 导出坐标

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "src", "dsr", "assets", "characters")


def sc(v):
    return v * S


def rrect(d, x0, y0, x1, y1, radius, fill=None, outline=None, width=0):
    d.rounded_rectangle([sc(x0), sc(y0), sc(x1), sc(y1)],
                        radius=sc(radius), fill=fill, outline=outline,
                        width=int(width * S))


def circle(d, cx, cy, r, fill=None, outline=None, width=0):
    d.ellipse([sc(cx - r), sc(cy - r), sc(cx + r), sc(cy + r)],
              fill=fill, outline=outline, width=int(width * S))


def ell(d, cx, cy, rx, ry, fill=None, outline=None, width=0):
    d.ellipse([sc(cx - rx), sc(cy - ry), sc(cx + rx), sc(cy + ry)],
              fill=fill, outline=outline, width=int(width * S))


def poly(d, pts, fill):
    d.polygon([(sc(x), sc(y)) for x, y in pts], fill=fill)


def arc(d, box, start, end, fill, width):
    d.arc([sc(box[0]), sc(box[1]), sc(box[2]), sc(box[3])],
          start=start, end=end, fill=fill, width=int(width * S))


def to_rgb(color):
    if isinstance(color, str):
        h = color.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    return tuple(color[:3])


def shade(color, f):
    """f<1 变暗，f>1 变亮。"""
    r, g, b = to_rgb(color)
    if f <= 1:
        return (int(r * f), int(g * f), int(b * f))
    t = min(f - 1.0, 1.0)
    return (int(r + (255 - r) * t), int(g + (255 - g) * t), int(b + (255 - b) * t))


# ---------------------------------------------------------------- 部件绘制

def hair_back(d, style, color):
    dark = shade(color, 0.78)
    if style in ("long", "bun", "twin"):
        # 披肩长发
        poly(d, [(150, 150), (362, 150), (376, 330), (350, 360),
                 (330, 300), (182, 300), (162, 360), (136, 330)], dark)
    # 头顶后发
    ell(d, 256, 152, 132, 134, dark)
    if style == "twin":
        circle(d, 104, 132, 52, dark)
        circle(d, 408, 132, 52, dark)


def head_base(d, skin):
    # 脖子
    rrect(d, 234, 250, 278, 300, 18, fill=shade(skin, 0.86))
    # 耳朵
    circle(d, 146, 186, 20, skin)
    circle(d, 366, 186, 20, skin)
    # 脸
    ell(d, 256, 168, 118, 112, skin)
    # 下巴补圆（让脸更饱满）
    ell(d, 256, 226, 92, 62, skin)


def hair_front(d, style, color):
    light = shade(color, 1.35)
    if style == "short":
        d.pieslice([sc(140), sc(60), sc(372), sc(268)], 180, 360, fill=color)
        poly(d, [(150, 160), (196, 122), (232, 158), (268, 120),
                 (312, 160), (352, 124), (368, 172), (150, 172)], color)
        # 高光
        ell(d, 216, 108, 42, 14, light)
    elif style == "bun":
        d.pieslice([sc(140), sc(60), sc(372), sc(268)], 180, 360, fill=color)
        ell(d, 168, 176, 34, 56, color)
        ell(d, 344, 176, 34, 56, color)
        ell(d, 200, 190, 30, 40, color)
        ell(d, 312, 190, 30, 40, color)
        ell(d, 256, 138, 108, 62, color)
        circle(d, 256, 52, 46, shade(color, 0.9))
        circle(d, 256, 52, 46, None)
        ell(d, 238, 36, 22, 12, light)
    elif style == "twin":
        d.pieslice([sc(140), sc(60), sc(372), sc(268)], 180, 360, fill=color)
        ell(d, 182, 178, 40, 58, color)
        ell(d, 330, 178, 40, 58, color)
        ell(d, 256, 130, 104, 58, color)
        ell(d, 236, 96, 34, 12, light)
    else:  # long
        d.pieslice([sc(140), sc(60), sc(372), sc(268)], 180, 360, fill=color)
        ell(d, 166, 190, 40, 74, color)
        ell(d, 346, 190, 40, 74, color)
        ell(d, 256, 132, 106, 60, color)
        ell(d, 300, 104, 40, 12, light)


def face(d, cfg):
    eye_c = cfg["eye"]
    x1, x2, ey = 206, 306, 200
    for x in (x1, x2):
        # 眼白
        ell(d, x, ey, 30, 33, (255, 255, 255))
        # 虹膜
        ell(d, x, ey + 3, 23, 25, eye_c)
        # 瞳孔
        ell(d, x, ey + 5, 14, 16, (34, 32, 46))
        # 高光
        circle(d, x - 9, ey - 8, 8, (255, 255, 255))
        circle(d, x + 8, ey + 14, 4, (255, 255, 255))
    # 睫毛/上眼线
    d.arc([sc(x1 - 30), sc(ey - 33), sc(x1 + 30), sc(ey + 33)], 200, 340,
          fill=cfg["line"], width=int(5 * S))
    d.arc([sc(x2 - 30), sc(ey - 33), sc(x2 + 30), sc(ey + 33)], 200, 340,
          fill=cfg["line"], width=int(5 * S))
    # 眉毛
    d.arc([sc(x1 - 32), sc(ey - 74), sc(x1 + 32), sc(ey - 30)], 200, 340,
          fill=cfg["hair"], width=int(7 * S))
    d.arc([sc(x2 - 32), sc(ey - 74), sc(x2 + 32), sc(ey - 30)], 200, 340,
          fill=cfg["hair"], width=int(7 * S))
    # 腮红
    blush = cfg["blush"]
    ell(d, 158, 236, 30, 18, blush)
    ell(d, 354, 236, 30, 18, blush)
    # 鼻子
    ell(d, 256, 228, 7, 5, shade(cfg["skin"], 0.88))
    # 微笑
    d.arc([sc(230), sc(236), sc(282), sc(276)], 20, 160,
          fill=cfg["line"], width=int(6 * S))
    # 嘴角
    circle(d, 231, 255, 4, cfg["line"])
    circle(d, 281, 255, 4, cfg["line"])


def body(d, cfg, style="shirt"):
    main = cfg["cloth"]
    trim = cfg["cloth2"]
    # 躯干
    rrect(d, 158, 288, 354, 452, 46, fill=main)
    # 领口
    poly(d, [(228, 288), (284, 288), (256, 330)], trim)
    # 袖子
    rrect(d, 112, 300, 168, 404, 26, fill=shade(main, 0.9))
    rrect(d, 344, 300, 400, 404, 26, fill=shade(main, 0.9))
    # 手
    circle(d, 140, 416, 25, cfg["skin"])
    circle(d, 372, 416, 25, cfg["skin"])
    # 腿
    rrect(d, 196, 440, 246, 476, 16, fill=shade(cfg["pants"], 0.95))
    rrect(d, 266, 440, 316, 476, 16, fill=shade(cfg["pants"], 0.95))
    # 鞋
    rrect(d, 182, 466, 254, 498, 16, fill=cfg["pants"])
    rrect(d, 258, 466, 330, 498, 16, fill=cfg["pants"])


def accessory(d, cfg, kind):
    if kind == "glasses":
        c = "#3b4252"
        d.rounded_rectangle([sc(168), sc(170), sc(244), sc(232)], radius=sc(14),
                            outline=c, width=int(6 * S))
        d.rounded_rectangle([sc(268), sc(170), sc(344), sc(232)], radius=sc(14),
                            outline=c, width=int(6 * S))
        d.line([sc(244), sc(196), sc(268), sc(196)], fill=c, width=int(6 * S))
        d.line([sc(168), sc(192), sc(146), sc(186)], fill=c, width=int(6 * S))
        d.line([sc(344), sc(192), sc(366), sc(186)], fill=c, width=int(6 * S))
    elif kind == "tie":
        c = "#d9534f"
        poly(d, [(256, 318), (276, 342), (262, 428), (250, 428), (236, 342)], c)
        poly(d, [(238, 306), (274, 306), (256, 322)], shade(c, 0.85))
    elif kind == "book":
        rrect(d, 296, 366, 404, 450, 10, fill="#f2b544")
        rrect(d, 296, 366, 320, 450, 6, fill="#d99a2b")
        # 手压在书上
        circle(d, 358, 366, 24, cfg["skin"])
        circle(d, 358, 366, 24, None)
    elif kind == "pointer":
        d.line([sc(368), sc(420), sc(452), sc(286)], fill="#8d6e63", width=int(9 * S))
        circle(d, 452, 286, 9, "#ef5b5b")
        circle(d, 372, 416, 25, cfg["skin"])


def sparkles(img):
    """在人物四角加几颗小星星，提升亲和力（不与人物重叠）。"""
    import math
    spots = ((40, 62, 15, "#ffd54f"), (476, 92, 12, "#ffd54f"),
             (30, 322, 10, "#ffe082"), (482, 300, 13, "#ffe082"))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x, y, r, col) in spots:
        x, y, r = x * K, y * K, r * K
        pts = []
        for i in range(8):
            a = math.pi / 4 * i - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.34
            pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
        d.polygon(pts, fill=col)
    return Image.alpha_composite(img, layer)


CHARACTERS = {
    "teacher_f": dict(
        kind="teacher", hair_style="bun", accessory="glasses",
        skin="#ffe0c4", hair="#4a3b34", eye="#5b8c5a", line="#3c3230",
        blush="#ffb3a7", cloth="#38b2ac", cloth2="#f7fafc", pants="#3d4c5c",
        art="老师·青",
    ),
    "teacher_m": dict(
        kind="teacher", hair_style="short", accessory="tie",
        skin="#ffdcc0", hair="#2f2a28", eye="#4a6fa5", line="#3c3230",
        blush="#ffb0a0", cloth="#5b9bd5", cloth2="#ffffff", pants="#3a4256",
        art="老师·蓝",
    ),
}
# 另外两个形象（绫宁宁 / 初音未来）是下载的 Q 版素材，
# 由 tools/make_guest_characters.py 生成，不在这里画。


def add_shadow(img):
    """给人物加一层柔和投影，使其在任意桌面壁纸上都能凸显出来。"""
    a = img.split()[3]
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.paste((28, 22, 44, 150), (0, 0), a)
    shadow = shadow.filter(ImageFilter.GaussianBlur(6 * K))
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.alpha_composite(shadow, (int(3 * K), int(6 * K)))
    out.alpha_composite(img)
    return out


def build(cfg):
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hair_back(d, cfg["hair_style"], cfg["hair"])
    body(d, cfg)
    head_base(d, cfg["skin"])
    hair_front(d, cfg["hair_style"], cfg["hair"])
    face(d, cfg)
    if cfg.get("accessory"):
        accessory(d, cfg, cfg["accessory"])
    img = img.resize((W, H), Image.LANCZOS)
    img = add_shadow(img)
    img = sparkles(img)
    return img

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, cfg in CHARACTERS.items():
        im = build(cfg)
        path = os.path.join(OUT_DIR, name + ".png")
        im.save(path)
        # 预览用白底大图
        prev = Image.new("RGB", im.size, (255, 255, 255))
        prev.paste(im, (0, 0), im)
        prev.save(os.path.join(OUT_DIR, "_preview_" + name + ".png"))
        print("saved", path, im.size)


if __name__ == "__main__":
    main()
