# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""离线渲染一张气泡预览图，用于调样式。"""
import os
import sys
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dsr import bubbledraw, paths  # noqa: E402


def main():
    chars = paths.builtin_characters()
    char_path = chars[0][2]
    spec = {
        "title": "老师好呀！有新文件啦～",
        "body": [
            "检测到从 U 盘复制过来的文件：",
            "《三年级数学第三单元测试卷.docx》",
            "建议把它复制到「数学」科目文件夹里。",
        ],
        "hint": "也可以直接点下面的按钮，我帮您移过去。",
        "buttons": [
            {"id": "move", "text": "移动到「数学」", "kind": "primary"},
            {"id": "other", "text": "放置在其他文件夹", "kind": "ghost"},
            {"id": "dismiss", "text": "知道了", "kind": "ghost"},
        ],
        "accent": "#2F855A",
        "character_path": char_path,
        "flip": False,
    }
    for scale in (1.0, 1.25):
        lay = bubbledraw.build_layout(spec, scale)
        img = bubbledraw.render(lay, hover_id="move")
        bg = Image.new("RGB", img.size, (46, 86, 132))
        bg.paste(img, (0, 0), img)
        out = r"D:\tixing\_scratch\bubble_%s.png" % str(scale).replace(".", "_")
        bg.save(out)
        print("saved", out, img.size)

    # 镜像布局
    spec2 = dict(spec)
    spec2["flip"] = True
    spec2["character_path"] = chars[3][2]
    spec2["title"] = "别忘了归档哦"
    spec2["body"] = ["《英语听力练习.mp3》", "看起来属于「英语」科目。"]
    spec2["hint"] = ""
    spec2["buttons"] = [
        {"id": "move", "text": "移动到「英语」", "kind": "primary"},
        {"id": "dismiss", "text": "稍后再说", "kind": "ghost"},
    ]
    lay = bubbledraw.build_layout(spec2, 1.0)
    img = bubbledraw.render(lay)
    bg = Image.new("RGB", img.size, (46, 86, 132))
    bg.paste(img, (0, 0), img)
    bg.save(r"D:\tixing\_scratch\bubble_flip.png")
    print("saved flip", img.size)


if __name__ == "__main__":
    main()
