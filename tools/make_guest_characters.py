# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""把下载来的 Q 版人物素材整理成软件用的 1024×1024 透明 PNG。

输入：`tools/guest_src/` 下的原始图片
输出：`src/dsr/assets/characters/teacher_miku.png`、`teacher_nene.png`、
     `teacher_nene_2.png`，以及同名 `_preview_*.png`（白底预览）

处理流程：取 alpha（自带 / AI 抠图）-> 归一化到 1024 画布
-> 加柔和投影 -> 加四角星星，风格与 `make_characters.py` 画出来的老师一致。

绫宁宁的两张图都走 AI 抠图（`tools/cutout_ai.py` 的 ISNet 动漫分割模型）；
`nene_b` 的棋盘格背景被模型误判成前景，用 `dechecker()` 再清一遍。
"""
from __future__ import annotations

import math
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cutout_ai  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "guest_src")
OUT = os.path.abspath(os.path.join(HERE, "..", "src", "dsr", "assets",
                                   "characters"))
W = H = 1024
SPARKLE = ((80, 124, 30, "#ffd54f"), (952, 184, 24, "#ffd54f"),
           (60, 644, 20, "#ffe082"), (964, 600, 26, "#ffe082"))


# ------------------------------------------------------------------ 抠背景
def _flood(near, seeds):
    """在 near 为真的区域里从 seeds 泛洪，返回可达掩码（原地 BFS）。"""
    h, w = near.shape
    seen = np.zeros((h, w), dtype=bool)
    q = deque()
    for (y, x) in seeds:
        if near[y, x] and not seen[y, x]:
            seen[y, x] = True
            q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and near[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


def _border_seeds(h, w):
    s = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)]
    s += [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
    return s


def _largest_blob(fg):
    """只保留最大的连通块（人物本体），丢掉背景里飘着的圆圈、签名等。"""
    h, w = fg.shape
    unknown = fg.copy()
    best, best_n = None, 0
    ys, xs = np.where(fg)
    for (sy, sx) in zip(ys.tolist(), xs.tolist()):
        if not unknown[sy, sx]:
            continue
        comp = _flood(unknown, [(sy, sx)])
        unknown &= ~comp
        n = int(comp.sum())
        if n > best_n:
            best, best_n = comp, n
    return best if best is not None else fg


def background_mask(im, scale=4, tol=26, feather=1.0, pale=200, grow=2):
    """抠掉浅色背景。

    在 1/scale 的分辨率上判断：先把"很浅"或"与边缘同色"的像素当背景候选，
    从四边泛洪得到背景；剩下的大块只留**最大的那一块**（人物），再补上它内部
    的孔洞，最后放大回原尺寸做成 alpha。
    这样人物周围飘着的浅色圆圈、背景签名都会被丢掉。
    """
    small = im.convert("RGB")
    sw, sh = max(1, small.size[0] // scale), max(1, small.size[1] // scale)
    small = small.resize((sw, sh), Image.BOX)
    rgb = np.asarray(small).astype(np.int16)
    border = np.concatenate([rgb[0, :, :], rgb[-1, :, :],
                             rgb[:, 0, :], rgb[:, -1, :]]).astype(np.float32)
    ref = np.median(border, axis=0)
    diff = np.abs(rgb.astype(np.float32) - ref).max(axis=2)
    near = (diff <= tol) | (rgb.min(axis=2) >= pale)

    bg = _flood(near, _border_seeds(sh, sw))
    blob = _largest_blob(~bg)
    # 填掉人物内部的孔洞（白头发、白帽子等被描边围住的浅色区域）
    blob_bg = _flood(~blob, _border_seeds(sh, sw))
    solid = ~blob_bg

    mask = Image.fromarray((solid * 255).astype(np.uint8), "L")
    mask = mask.resize(im.size, Image.LANCZOS)
    if grow:
        mask = mask.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather))
    arr = np.asarray(im.convert("RGBA")).copy()
    arr[:, :, 3] = np.asarray(mask)
    return Image.fromarray(arr, "RGBA")


def trim(img, pad=2):
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0) \
        .getbbox()
    if not bbox:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - pad); y0 = max(0, y0 - pad)
    x1 = min(img.size[0], x1 + pad); y1 = min(img.size[1], y1 + pad)
    return img.crop((x0, y0, x1, y1))


def normalize(img, frac=0.94):
    """等比缩放到高度约 frac*H，水平居中，底部贴近画布下沿。"""
    img = trim(img)
    target_h = int(H * frac)
    scale = target_h / float(img.size[1])
    if img.size[0] * scale > W * 0.98:
        scale = W * 0.98 / float(img.size[0])
    size = (max(1, int(img.size[0] * scale)), max(1, int(img.size[1] * scale)))
    img = img.resize(size, Image.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((W - size[0]) // 2, H - size[1] - 8))
    return canvas


def add_shadow(img, blur=9, offset=(4, 7), alpha=150):
    a = img.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(a.point(lambda v: int(v * alpha / 255.0)))
    shadow = Image.merge("RGBA", (
        Image.new("L", img.size, 28), Image.new("L", img.size, 22),
        Image.new("L", img.size, 44), shadow.getchannel("A")))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(shadow, offset)
    layer.alpha_composite(img)
    return layer


def sparkles(img):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x, y, r, col) in SPARKLE:
        pts = []
        for i in range(8):
            a = math.pi / 4 * i - math.pi / 2
            rr = r if i % 2 == 0 else r * 0.34
            pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
        d.polygon(pts, fill=col)
    return Image.alpha_composite(img, layer)


# ------------------------------------------------------------------ 主流程
def ai_alpha(im, lo=0.15, hi=0.85, session=None):
    """用 ISNet 动漫分割模型算 alpha（0~1 float）。"""
    a = cutout_ai.raw_alpha(im, session)
    return np.clip((a - lo) / max(hi - lo, 1e-6), 0.0, 1.0)


def dechecker(im, alpha, min_area=3000, bg_frac=0.25):
    """清掉「AI 把棋盘格背景当人物」的残留。

    棋盘格在局部（两个周期 ≈ 39px）内的亮度起伏约 18~45，而人物头发、
    衣服是均匀色，局部起伏极小 —— 用这个特征把棋盘格找出来；再要求该连通块
    足够大、且真的挨着 AI 判定的背景，避免把头发上正常的高光挖出小洞。
    """
    rgb = np.asarray(im.convert("RGB")).astype(np.float32)
    g = rgb.mean(axis=2)
    rng = ndimage.maximum_filter(g, 39) - ndimage.minimum_filter(g, 39)
    mx = rgb.max(axis=2)
    mn = rgb.min(axis=2)
    ck = (rng > 18) & (rng < 45) & ((mx - mn) <= 14) & (mn >= 205)
    ck = ndimage.binary_closing(ck, np.ones((9, 9)))
    ck = ndimage.binary_opening(ck, np.ones((9, 9)))
    lab, n = ndimage.label(ck)
    bgd = ndimage.binary_dilation(alpha < 0.05, np.ones((25, 25)))
    keep = np.zeros_like(ck)
    for i in range(1, n + 1):
        comp = (lab == i)
        if comp.sum() < min_area:
            continue
        if (comp & bgd).sum() < bg_frac * comp.sum():
            continue
        keep |= comp
    m = Image.fromarray((keep * 255).astype("uint8"), "L") \
        .filter(ImageFilter.GaussianBlur(3))
    s = np.asarray(m).astype(np.float32) / 255.0
    return np.clip(alpha * (1.0 - s), 0.0, 1.0)


def with_alpha(im, alpha):
    out = im.convert("RGBA").copy()
    out.putalpha(Image.fromarray((np.clip(alpha, 0, 1) * 255).astype("uint8"), "L"))
    return out


JOBS = (
    # 源文件,           输出 id,            显示名,          alpha 来源
    ("hatsune_miku.png", "teacher_miku",   "初音未来（青绿）", "keep"),
    ("nene_a.png",       "teacher_nene",   "绫宁宁（紫）",     "ai"),
    ("nene_b.png",       "teacher_nene_2", "绫宁宁（紫）",     "ai-dechecker"),
)


def main():
    os.makedirs(OUT, exist_ok=True)
    session = None
    for src, cid, label, mode in JOBS:
        p = os.path.join(SRC, src)
        if not os.path.isfile(p):
            print("缺少素材：%s" % p)
            return 1
        im = Image.open(p)
        if mode == "keep":
            im = im.convert("RGBA")
        else:
            if session is None:
                session = cutout_ai._session()
            a = ai_alpha(im, session=session)
            if mode == "ai-dechecker":
                a = dechecker(im, a)
            im = with_alpha(im, a)
        im = normalize(im)
        im = add_shadow(im)
        im = sparkles(im)
        dst = os.path.join(OUT, cid + ".png")
        im.save(dst)
        preview = Image.new("RGB", im.size, (255, 255, 255))
        preview.paste(im, (0, 0), im)
        preview.save(os.path.join(OUT, "_preview_" + cid + ".png"))
        alpha = im.getchannel("A")
        print("%-16s %-14s -> %s  alpha=%s  corner=%s"
              % (src, label, os.path.basename(dst), alpha.getextrema(),
                 alpha.getpixel((0, 0))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
