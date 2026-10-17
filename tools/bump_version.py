# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""统一升版本号：paths.py 的 APP_VERSION + PyInstaller 的 version_info.txt。

用法::  python bump_version.py 1.2.0
"""
from __future__ import annotations

import io
import re
import sys

P1 = r"D:\tixing\src\dsr\paths.py"
P2 = r"D:\tixing\tools\version_info.txt"


def main():
    new = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", new):
        print("用法：python bump_version.py <版本号，如 1.2.0>")
        return 2
    quad = "(%s, 0)" % ", ".join(new.split("."))
    quad4 = "(%s, 0)" % ", ".join(new.split("."))

    s = io.open(P1, encoding="utf-8").read()
    m = re.search(r'APP_VERSION\s*=\s*"([^"]*)"', s)
    old = m.group(1) if m else "?"
    s2 = re.sub(r'APP_VERSION\s*=\s*"[^"]*"', 'APP_VERSION = "%s"' % new, s)
    io.open(P1, "w", encoding="utf-8", newline="\n").write(s2)
    print("paths.py: %s -> %s %s" % (old, new, "ok" if s2 != s else "unchanged"))

    t = io.open(P2, encoding="utf-8").read()
    t2 = re.sub(r"filevers=\([^)]*\)", "filevers=" + quad4, t)
    t2 = re.sub(r"prodvers=\([^)]*\)", "prodvers=" + quad4, t2)
    t2 = re.sub(r"FileVersion',\s*u?'[^']*'", "FileVersion', u'%s.0'" % new, t2)
    t2 = re.sub(r"ProductVersion',\s*u?'[^']*'",
                "ProductVersion', u'%s.0'" % new, t2)
    io.open(P2, "w", encoding="utf-8", newline="\r\n").write(t2)
    print("version_info.txt:", "ok" if t2 != t else "unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
