# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 classDesktopManager contributors

"""人物对话气泡窗口（Win32 分层窗口 + 逐像素 alpha）。

必须在带消息循环的线程上创建，见 :mod:`dsr.uithread`。
"""
from __future__ import annotations

import ctypes
import time

from PIL import Image, ImageChops

from . import bubbledraw, winapi

user32 = winapi.user32
gdi32 = winapi.gdi32

# 触摸 API（老系统上可能没有，取不到就退化成纯鼠标）
_touch_api = {}
try:
    _rtw = getattr(user32, "RegisterTouchWindow", None)
    _gtii = getattr(user32, "GetTouchInputInfo", None)
    _ctih = getattr(user32, "CloseTouchInputHandle", None)
    if _rtw and _gtii and _ctih:
        _rtw.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.ULONG]
        _rtw.restype = ctypes.wintypes.BOOL
        _gtii.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p,
                          ctypes.c_int]
        _gtii.restype = ctypes.wintypes.BOOL
        _ctih.argtypes = [ctypes.c_void_p]
        _ctih.restype = ctypes.wintypes.BOOL
        _touch_api = {"reg": _rtw, "get": _gtii, "close": _ctih}
except Exception:                                   # pragma: no cover
    _touch_api = {}

_CLASS = "DsrBubbleWnd"
_atom = None
_wndproc_ref = None
_windows = {}

TIMER_ANIM = 1
TIMER_LIFE = 2

STYLE_EX = (winapi.WS_EX_LAYERED | winapi.WS_EX_TOPMOST |
            winapi.WS_EX_TOOLWINDOW | winapi.WS_EX_NOACTIVATE)

FADE_MS = 200.0
SLIDE_PX = 14


def _pt(lparam):
    x = lparam & 0xFFFF
    y = (lparam >> 16) & 0xFFFF
    if x >= 0x8000:
        x -= 0x10000
    if y >= 0x8000:
        y -= 0x10000
    return x, y


def _in_rect(r, x, y):
    return r and r[0] <= x < r[2] and r[1] <= y < r[3]


# --- 触摸支持 ---------------------------------------------------------
WM_TOUCH = 0x0240
TWF_WANTPALM = 0x00000001
TOUCHEVENTF_MOVE = 0x0001
TOUCHEVENTF_DOWN = 0x0002
TOUCHEVENTF_UP = 0x0004

# 手指点按比鼠标"抖"，按下后位移超过这个逻辑像素数才算拖动
DRAG_SLOP = 7
# 触摸后多久内忽略系统补发的鼠标消息（防止一次点按触发两次）
TOUCH_MOUSE_GUARD = 0.7
# 触摸目标最小边长（逻辑像素），Windows 人机界面指南建议 44
MIN_TOUCH = 44


class TOUCHINPUT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),          # 屏幕坐标，单位 1/100 像素
        ("y", ctypes.c_long),
        ("hSource", ctypes.c_void_p),
        ("dwID", ctypes.wintypes.DWORD),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("dwMask", ctypes.wintypes.DWORD),
        ("dwTime", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
        ("cxContact", ctypes.wintypes.DWORD),
        ("cyContact", ctypes.wintypes.DWORD),
    ]


def ensure_class():
    global _atom, _wndproc_ref
    if _atom:
        return _atom
    hinst = winapi.kernel32.GetModuleHandleW(None)
    _wndproc_ref = winapi.WNDPROC(_wndproc)
    wc = winapi.WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(winapi.WNDCLASSEXW)
    wc.style = 0
    wc.lpfnWndProc = _wndproc_ref
    wc.cbClsExtra = 0
    wc.cbWndExtra = 0
    wc.hInstance = hinst
    wc.hIcon = None
    wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(winapi.IDC_ARROW_))
    wc.hbrBackground = None
    wc.lpszMenuName = None
    wc.lpszClassName = _CLASS
    wc.hIconSm = None
    _atom = user32.RegisterClassExW(ctypes.byref(wc))
    return _atom


def _wndproc(hwnd, msg, wparam, lparam):
    win = _windows.get(int(hwnd or 0))
    if win is None:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    try:
        return win.on_message(msg, wparam, lparam)
    except Exception:
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


# ------------------------------------------------------------------ 窗口
class BubbleWindow:
    def __init__(self, manager, spec, scale=1.0, corner="br", duration=14.0,
                 on_action=None, on_closed=None):
        self.manager = manager
        self.spec = spec
        self.scale = scale
        self.corner = corner
        self.duration = max(0.0, float(duration))
        self.on_action = on_action
        self.on_closed = on_closed

        self.hwnd = None
        self.layout = bubbledraw.build_layout(spec, scale)
        self.width = self.layout.width
        self.height = self.layout.height
        self.x = 0
        self.y = 0
        self.base_x = 0
        self.base_y = 0
        self.stack_offset = 0

        self._memdc = None
        self._hbmp = None
        self._old_bmp = None
        self._ppv = None
        self._last_img = None

        self._hover = None
        self._pressed = None
        self._mouse_inside = False
        self._dragging = False
        self._drag_org = (0, 0)
        self._drag_start = (0, 0)
        self._drag_slop = int(DRAG_SLOP * max(1.0, float(scale)))
        self._moved = False
        self._touch_seen = 0.0
        self._touch_pressed = None
        self._touch_registered = False

        self._alpha = 0
        self._anim_state = "in"
        self._anim_t0 = time.time()
        self._remaining = self.duration
        self._dead = False

    # -------------------------------------------------------------- 生命周期
    def create(self):
        ensure_class()
        hinst = winapi.kernel32.GetModuleHandleW(None)
        self.hwnd = user32.CreateWindowExW(
            STYLE_EX, _CLASS, "科目文件夹提醒", winapi.WS_POPUP,
            0, 0, self.width, self.height, None, None, hinst, None)
        if not self.hwnd:
            raise OSError("创建气泡窗口失败")
        _windows[int(self.hwnd)] = self
        self._register_touch()
        img = bubbledraw.render(self.layout)
        self._paint(img, alpha=0)
        user32.ShowWindow(self.hwnd, winapi.SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, winapi.HWND_TOPMOST, 0, 0, 0, 0,
                            winapi.SWP_NOMOVE | winapi.SWP_NOSIZE |
                            winapi.SWP_NOACTIVATE)
        user32.SetTimer(self.hwnd, TIMER_ANIM, 20, None)
        if self.duration > 0:
            user32.SetTimer(self.hwnd, TIMER_LIFE, 1000, None)
        return self

    def _register_touch(self):
        """注册触摸输入，让手指直接点按也能触发按钮。"""
        reg = _touch_api.get("reg")
        if reg is None or not self.hwnd:
            return
        try:
            self._touch_registered = bool(reg(self.hwnd, TWF_WANTPALM))
        except Exception:
            self._touch_registered = False

    def destroy(self):
        if self._dead:
            return
        self._dead = True
        if self.hwnd:
            user32.KillTimer(self.hwnd, TIMER_ANIM)
            user32.KillTimer(self.hwnd, TIMER_LIFE)
            _windows.pop(int(self.hwnd), None)
            user32.DestroyWindow(self.hwnd)
            self.hwnd = None
        self._free_bitmap()
        if self.on_closed:
            try:
                self.on_closed(self)
            except Exception:
                pass

    def _free_bitmap(self):
        try:
            if self._memdc and self._old_bmp:
                gdi32.SelectObject(self._memdc, self._old_bmp)
            if self._hbmp:
                gdi32.DeleteObject(self._hbmp)
            if self._memdc:
                gdi32.DeleteDC(self._memdc)
        except Exception:
            pass
        self._memdc = self._hbmp = self._old_bmp = None

    # ------------------------------------------------------------ 绘制/呈现
    def _paint(self, img, alpha=255):
        img = img.convert("RGBA")
        w, h = img.size
        bmi = winapi.BITMAPINFO()
        hdr = bmi.bmiHeader
        hdr.biSize = ctypes.sizeof(winapi.BITMAPINFOHEADER)
        hdr.biWidth = w
        hdr.biHeight = -h
        hdr.biPlanes = 1
        hdr.biBitCount = 32
        hdr.biCompression = winapi.DIB_RGB_COLORS
        hdr.biSizeImage = w * h * 4

        screen_dc = user32.GetDC(None)
        if not screen_dc:
            return
        try:
            self._free_bitmap()
            ppv = ctypes.c_void_p()
            hbmp = gdi32.CreateDIBSection(screen_dc, ctypes.byref(bmi),
                                          winapi.DIB_RGB_COLORS,
                                          ctypes.byref(ppv), None, 0)
            if not hbmp:
                return
            memdc = gdi32.CreateCompatibleDC(screen_dc)
            old = gdi32.SelectObject(memdc, hbmp)
            self._memdc, self._hbmp, self._old_bmp, self._ppv = \
                memdc, hbmp, old, ppv

            r, g, b, a = img.split()
            prem = Image.merge("RGBA", (ImageChops.multiply(b, a),
                                        ImageChops.multiply(g, a),
                                        ImageChops.multiply(r, a), a))
            data = prem.tobytes()
            ctypes.memmove(ppv, data, len(data))
            self._blit(alpha)
            self._last_img = img
        finally:
            user32.ReleaseDC(None, screen_dc)

    def _blit(self, alpha=255):
        if not self.hwnd or not self._memdc:
            return
        screen_dc = user32.GetDC(None)
        try:
            pt_dst = winapi.POINT(self.x, self.y)
            size = winapi.SIZE(self.width, self.height)
            pt_src = winapi.POINT(0, 0)
            blend = winapi.BLENDFUNCTION(winapi.AC_SRC_OVER, 0,
                                         max(0, min(255, int(alpha))),
                                         winapi.AC_SRC_ALPHA)
            user32.UpdateLayeredWindow(
                self.hwnd, screen_dc, ctypes.byref(pt_dst), ctypes.byref(size),
                self._memdc, ctypes.byref(pt_src), 0, ctypes.byref(blend),
                winapi.ULW_ALPHA)
        finally:
            user32.ReleaseDC(None, screen_dc)

    def redraw(self):
        img = bubbledraw.render(self.layout, hover_id=self._hover,
                                pressed_id=self._pressed)
        self._paint(img, alpha=self._alpha)

    # ---------------------------------------------------------------- 定位
    def place(self, x, y):
        """设置窗口左上角（物理像素）。"""
        self.base_x, self.base_y = int(x), int(y)
        self.x = self.base_x
        self.y = self.base_y + (SLIDE_PX if self._anim_state == "in" else 0)
        self._blit(self._alpha)

    def move(self, x, y):
        self.base_x, self.base_y = int(x), int(y)
        self.x, self.y = int(x), int(y)
        self._blit(self._alpha)

    # ---------------------------------------------------------------- 消息
    def on_message(self, msg, wparam, lparam):
        if msg == winapi.WM_TIMER:
            if wparam == TIMER_ANIM:
                self._tick_anim()
            elif wparam == TIMER_LIFE:
                self._tick_life()
            return 0
        if msg == winapi.WM_MOUSEMOVE:
            self._on_mouse_move(lparam)
            return 0
        if msg == winapi.WM_MOUSELEAVE:
            self._mouse_inside = False
            self._hover = None
            self._pressed = None
            self.redraw()
            return 0
        if msg == winapi.WM_LBUTTONDOWN:
            self._on_lbutton_down(lparam)
            return 0
        if msg == winapi.WM_LBUTTONUP:
            self._on_lbutton_up(lparam)
            return 0
        if msg == winapi.WM_RBUTTONUP:
            if self.layout.closable:
                self.begin_close()
            return 0
        if msg == winapi.WM_CAPTURECHANGED:
            self._dragging = False
            return 0
        if msg == winapi.WM_SETCURSOR:
            if self._hover:
                user32.SetCursor(user32.LoadCursorW(
                    None, ctypes.c_void_p(winapi.IDC_HAND)))
                return 1
            return user32.DefWindowProcW(self.hwnd, msg, wparam, lparam)
        if msg == WM_TOUCH:
            return self._on_touch(wparam, lparam)
        if msg == winapi.WM_NCHITTEST:
            return self._hit_test(lparam)
        if msg == winapi.WM_ERASEBKGND:
            return 1
        if msg == winapi.WM_DESTROY:
            self._dead = True
            _windows.pop(int(self.hwnd or 0), None)
            return 0
        return user32.DefWindowProcW(self.hwnd, msg, wparam, lparam)

    def _hit_test(self, lparam):
        """透明像素处让鼠标穿透，其余返回 HTCLIENT。"""
        x, y = _pt(lparam)
        rect = winapi.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        cx, cy = x - rect.left, y - rect.top
        if self._last_img is None:
            return winapi.HTCLIENT
        if 0 <= cx < self.width and 0 <= cy < self.height:
            try:
                if self._last_img.getpixel((cx, cy))[3] < 12:
                    return winapi.HTTRANSPARENT
            except Exception:
                pass
            return winapi.HTCLIENT
        return winapi.HTTRANSPARENT

    def _screen_to_client(self, lparam):
        """WM_NCHITTEST 的 lParam 是屏幕坐标，需要换算成客户区坐标。"""
        x, y = _pt(lparam)
        rect = winapi.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        return x - rect.left, y - rect.top

    def _client_pt(self, lparam):
        """WM_MOUSE*/WM_LBUTTON* 的 lParam **本来就是客户区坐标**。

        早期版本这里错用了 _screen_to_client()，把客户区坐标又减了一次窗口
        原点，导致按钮永远命中不了（点不动的根因）。
        """
        return _pt(lparam)

    # ------------------------------------------------------------ 命中判定
    def _button_at(self, cx, cy):
        """按钮命中。轻微外扩，方便鼠标/手指点在边上也能中。"""
        slop = int(5 * self.scale)
        for (x0, y0, x1, y1, bid, _kind) in self.layout.buttons:
            if (x0 - slop <= cx < x1 + slop) and (y0 - slop <= cy < y1 + slop):
                return bid
        return None

    def _close_hit(self):
        """关闭按钮的命中矩形，触摸时至少 44 逻辑像素见方。

        强制归档（closable=False）时没有关闭键，返回 None。
        """
        if not self.layout.closable:
            return None
        x0, y0, x1, y1 = self.layout.close_rect
        need = int(MIN_TOUCH * self.scale)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        hw = max(x1 - x0, need) / 2.0
        hh = max(y1 - y0, need) / 2.0
        return (cx - hw, cy - hh, cx + hw, cy + hh)

    def _close_at(self, cx, cy):
        rect = self._close_hit()
        return bool(rect) and _in_rect(rect, cx, cy)

    def _on_mouse_move(self, lparam):
        cx, cy = self._client_pt(lparam)
        if not self._mouse_inside:
            self._mouse_inside = True
            tme = winapi.TRACKMOUSEEVENT()
            tme.cbSize = ctypes.sizeof(winapi.TRACKMOUSEEVENT)
            tme.dwFlags = winapi.TME_LEAVE
            tme.hwndTrack = self.hwnd
            tme.dwHoverTime = 0
            user32.TrackMouseEvent(ctypes.byref(tme))

        if self._dragging:
            x, y = cx, cy
            dx = x - self._drag_start[0]
            dy = y - self._drag_start[1]
            if abs(dx) > self._drag_slop or abs(dy) > self._drag_slop:
                self._moved = True
            if self._moved:
                self.move(self._drag_org[0] + dx, self._drag_org[1] + dy)
            return

        bid = self._button_at(cx, cy)
        if bid is None and self._close_at(cx, cy):
            bid = "__close"
        if bid != self._hover:
            self._hover = bid
            self.redraw()

    def _on_lbutton_down(self, lparam):
        if time.time() - self._touch_seen < TOUCH_MOUSE_GUARD:
            return
        cx, cy = self._client_pt(lparam)
        if self._close_at(cx, cy):
            self.begin_close()
            return
        bid = self._button_at(cx, cy)
        self._dragging = True
        self._moved = False
        self._drag_slop = int(DRAG_SLOP * self.scale)
        self._drag_org = (self.x, self.y)
        self._drag_start = (cx, cy)
        user32.SetCapture(self.hwnd)
        if bid:
            self._pressed = bid
            self.redraw()

    def _on_lbutton_up(self, lparam):
        if time.time() - self._touch_seen < TOUCH_MOUSE_GUARD:
            return
        cx, cy = self._client_pt(lparam)
        user32.ReleaseCapture()
        self._dragging = False
        bid = self._button_at(cx, cy)
        was = self._pressed
        self._pressed = None
        self.redraw()
        if was and bid == was:
            self.fire(was)

    # ---------------------------------------------------------------- 触摸
    def _on_touch(self, wparam, lparam):
        n = int(wparam)
        if n <= 0:
            return 0
        info = _touch_api.get("get")
        if info is None:
            return user32.DefWindowProcW(self.hwnd, WM_TOUCH, wparam, lparam)
        arr = (TOUCHINPUT * n)()
        if not info(ctypes.c_void_p(lparam), n, ctypes.byref(arr),
                    ctypes.sizeof(TOUCHINPUT)):
            return 0
        self._touch_seen = time.time()
        try:
            for t in arr:
                # 触摸坐标单位是 1/100 像素
                sx, sy = t.x / 100.0, t.y / 100.0
                cx, cy = self._screen_to_client(
                    (int(sy) & 0xFFFF) << 16 | (int(sx) & 0xFFFF))
                if t.dwFlags & TOUCHEVENTF_DOWN:
                    self._touch_down(cx, cy)
                elif t.dwFlags & TOUCHEVENTF_UP:
                    self._touch_up(cx, cy)
                elif t.dwFlags & TOUCHEVENTF_MOVE:
                    self._touch_move(cx, cy)
        finally:
            _touch_api["close"](ctypes.c_void_p(lparam))
        return 0

    def _touch_down(self, cx, cy):
        self._touch_seen = time.time()
        if self._close_at(cx, cy):
            self._touch_pressed = "__close"
            self.begin_close()
            return
        bid = self._button_at(cx, cy)
        self._touch_pressed = bid
        self._drag_org = (self.x, self.y)
        self._drag_start = (cx, cy)
        self._drag_slop = int(DRAG_SLOP * 2 * self.scale)   # 手指抖得更厉害
        self._moved = False
        self._dragging = bool(bid is None)
        if bid:
            self._pressed = bid
            self.redraw()

    def _touch_move(self, cx, cy):
        self._touch_seen = time.time()
        if not self._dragging:
            return
        dx = cx - self._drag_start[0]
        dy = cy - self._drag_start[1]
        if abs(dx) > self._drag_slop or abs(dy) > self._drag_slop:
            self._moved = True
        if self._moved:
            self.move(self._drag_org[0] + dx, self._drag_org[1] + dy)

    def _touch_up(self, cx, cy):
        self._touch_seen = time.time()
        was = self._touch_pressed
        self._touch_pressed = None
        self._dragging = False
        if was == "__close":
            return
        bid = self._button_at(cx, cy)
        self._pressed = None
        self.redraw()
        if was and bid == was:
            self.fire(was)

    # ---------------------------------------------------------------- 动作
    def fire(self, action_id):
        if action_id in ("close", "dismiss"):
            self.begin_close()
            return
        if self.on_action:
            try:
                self.on_action(action_id, self)
            except Exception:
                pass

    def begin_close(self):
        if self._dead or self._anim_state == "out":
            return
        self._anim_state = "out"
        self._anim_t0 = time.time()
        user32.SetTimer(self.hwnd, TIMER_ANIM, 20, None)
        user32.KillTimer(self.hwnd, TIMER_LIFE)

    def hold(self):
        """重新计时（鼠标移入时暂停自动关闭）。"""
        self._remaining = self.duration

    # ---------------------------------------------------------------- 动画
    def _tick_anim(self):
        if self._dead:
            return
        t = (time.time() - self._anim_t0) * 1000.0
        k = min(1.0, t / FADE_MS)
        if self._anim_state == "in":
            self._alpha = int(255 * k)
            self.y = self.base_y + int(SLIDE_PX * (1.0 - k))
            self._blit(self._alpha)
            if k >= 1.0:
                self._alpha = 255
                self.y = self.base_y
                self._blit(255)
                self._anim_state = "live"
                user32.KillTimer(self.hwnd, TIMER_ANIM)
        elif self._anim_state == "out":
            self._alpha = int(255 * (1.0 - k))
            self.y = self.base_y + int(8 * k)
            self._blit(self._alpha)
            if k >= 1.0:
                user32.KillTimer(self.hwnd, TIMER_ANIM)
                self.destroy()

    def _tick_life(self):
        if self._dead or self._anim_state != "live":
            return
        if self._mouse_inside or self._dragging or self._pressed:
            self._remaining = self.duration
            return
        self._remaining -= 1.0
        if self._remaining <= 0:
            self.begin_close()


# ---------------------------------------------------------------- 管理器
class BubbleManager:
    """在 UI 线程上管理最多 N 个气泡，靠近屏幕某一个角堆叠。"""

    def __init__(self, scale=1.0, margin=22, max_bubbles=3):
        self.scale = scale
        self.margin = margin
        self.max_bubbles = max_bubbles
        self.windows = []
        self.on_action = None

    # ---- 布局
    def _layout_positions(self):
        # 用鼠标所在那块屏的工作区与缩放比：多屏 + 每屏不同 DPI 时才正确
        left, top, right, bottom = winapi.monitor_work_area()
        s = winapi.dpi_scale_for_point()
        gap = int(10 * s)
        margin = int(self.margin * s)
        ys = {}
        # 从下往上堆叠
        cursor_y = bottom - margin
        for win in reversed(self.windows):
            cursor_y -= win.height
            ys[id(win)] = cursor_y
            cursor_y -= gap
        out = []
        for win in self.windows:
            corner = win.corner
            if corner in ("br", "tr"):
                x = right - margin - win.width
            else:
                x = left + margin
            if corner in ("br", "bl"):
                y = ys.get(id(win), bottom - margin - win.height)
            else:
                y = top + margin
            out.append((win, x, y))
        return out

    def _reposition(self):
        for win, x, y in self._layout_positions():
            if win.hwnd:
                win.place(x, y)

    # ---- 对外
    def show(self, spec, corner="br", duration=14.0, on_action=None):
        while len(self.windows) >= self.max_bubbles:
            old = self.windows[0]
            self.windows.remove(old)
            old.destroy()
        scale = winapi.dpi_scale_for_point()
        win = BubbleWindow(self, spec, scale=scale, corner=corner,
                           duration=duration, on_action=on_action,
                           on_closed=self._on_closed)
        win.create()
        self.windows.append(win)
        self._reposition()
        return win

    def _on_closed(self, win):
        if win in self.windows:
            self.windows.remove(win)
        try:
            self._reposition()
        except Exception:
            pass

    def close_all(self):
        for win in list(self.windows):
            win.destroy()
        self.windows = []

    def count(self):
        return len(self.windows)
