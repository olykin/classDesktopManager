# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""高精度抠图：用动漫专用的 ISNet 分割模型（anime-seg / isnetis）算出 alpha。

用法::

    python tools\\cutout_ai.py <输入图片> <输出PNG> [--lo 0.15] [--hi 0.85] [--grow 0] [--feather 0.6]

模型放在 ``tools/models/isnetis.onnx``（HF 镜像 skytnt/anime-seg）。
输出为同尺寸 RGBA PNG。

为什么不用 rembg：rembg 2.0.85 的 ``isnet-anime`` 会从 GitHub Releases 下载，
本机访问 GitHub 超时；这里直接用 onnxruntime 调同一个模型，顺便自己控制
预处理与 alpha 处理。模型的 ``mask`` 输出**已经是 0~1 的概率**，不要再做
sigmoid（再套一层 sigmoid 会把结果压到 0.5~0.73，边缘全糊）。
"""
from __future__ import annotations

import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE = 1024
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)

# 模型有 168 MB，不放进仓库：优先环境变量，其次用户目录，最后才是 tools/models。
# 下载（本机 GitHub 不通，用 HF 镜像）：
#   curl -L -o %LOCALAPPDATA%\dsr-models\isnetis.onnx \
#     https://hf-mirror.com/skytnt/anime-seg/resolve/main/isnetis.onnx
MODEL_NAME = "isnetis.onnx"
MODEL_DIRS = (
    os.environ.get("DSR_MODEL_DIR"),
    os.path.join(os.environ.get("LOCALAPPDATA") or "", "dsr-models"),
    os.path.join(HERE, "models"),
)


def model_path():
    for d in MODEL_DIRS:
        if d:
            p = os.path.join(d, MODEL_NAME)
            if os.path.isfile(p):
                return p
    raise FileNotFoundError(
        "找不到 %s，请放到 %s" % (MODEL_NAME, MODEL_DIRS[1]))


def _session():
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    return ort.InferenceSession(model_path(), sess_options=opts,
                                providers=["CPUExecutionProvider"])


def raw_alpha(im, session=None):
    """返回与原图同尺寸的 float32 alpha（0~1）。"""
    session = session or _session()
    im = im.convert("RGB")
    w, h = im.size
    small = im.resize((SIZE, SIZE), Image.LANCZOS)
    x = np.asarray(small).astype(np.float32) / 255.0
    x = ((x - MEAN) / STD).transpose(2, 0, 1)[None].copy()
    out = session.run(None, {session.get_inputs()[0].name: x})[0]
    a = np.clip(np.asarray(out).reshape(SIZE, SIZE), 0.0, 1.0)
    a = Image.fromarray((a * 255.0).astype("uint8"), "L").resize((w, h),
                                                                 Image.LANCZOS)
    return np.asarray(a).astype(np.float32) / 255.0


def cut(src, dst, lo=0.15, hi=0.85, grow=0, feather=0.6, session=None):
    """把 src 抠成带 alpha 的 PNG 写到 dst。

    lo/hi：把 alpha 线性拉伸，小于 lo 的判为背景、大于 hi 的判为前景，
            中间保留为抗锯齿过渡带（越小过渡越窄、边缘越硬）。
    grow：先向外扩 n 像素（补回被模型吃掉的白色贴纸描边）。
    feather：最后做的高斯羽化半径（0 = 不羽化）。
    """
    session = session or _session()
    im = Image.open(src)
    a = raw_alpha(im, session)
    if lo > 0 or hi < 1:
        a = np.clip((a - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    mask = Image.fromarray((a * 255.0).astype("uint8"), "L")
    if grow > 0:
        mask = mask.filter(ImageFilter.MaxFilter(int(grow) * 2 + 1))
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(float(feather)))
    out = im.convert("RGBA")
    out.putalpha(mask)
    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
    out.save(dst)
    ex = mask.getextrema()
    print("saved %s %s alpha=%s" % (dst, out.size, ex), flush=True)
    return dst


def main(argv):
    args = [a for a in argv[1:]]
    if len(args) < 2:
        print(__doc__)
        return 2
    src, dst = args[0], args[1]
    kw = {}
    i = 2
    while i + 1 < len(args):
        k, v = args[i].lstrip("-"), args[i + 1]
        kw[k] = float(v)
        i += 2
    cut(src, dst, **kw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
