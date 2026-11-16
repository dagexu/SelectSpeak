"""悬浮控制条：无边框、置顶、不抢焦点，全部 Canvas 自绘。"""
import ctypes
import tkinter as tk
import tkinter.font as tkfont

from config import DEFAULT_VOICES

BG = "#1b1b20"
BORDER = "#34343d"
TXT = "#e9e9ec"
SUBTLE = "#8b8b96"
ACCENT = "#4c8dff"
ACCENT_DIM = "#2f5aa8"
HOVER = "#2b2b33"
TRACK = "#3a3a44"
KEYCOLOR = "#010203"

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class FloatBar:
    W, H = 460, 92

    def __init__(self, root: tk.Tk, config, callbacks: dict, logger=None):
        self.root = root
        self.cfg = config
        self.cb = callbacks
        self._log = logger or (lambda *a: None)
        self._scale = self._detect_scale()
        self._hide_job = None
        self._hover = False
        self._last_drawn = {}

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=KEYCOLOR)
        try:
            self.win.attributes("-transparentcolor", KEYCOLOR)
        except Exception:
            pass

        self.f_preview = tkfont.Font(
            family="Microsoft YaHei UI", size=max(9, self.s(10))
        )
        self.f_small = tkfont.Font(
            family="Microsoft YaHei UI", size=max(8, self.s(9))
        )

        W, H = self.s(self.W), self.s(self.H)
        self.cv = tk.Canvas(
            self.win, width=W, height=H, bg=KEYCOLOR, highlightthickness=0, bd=0
        )
        self.cv.pack()

        self._place_window()
        self._make_noactivate()
        self._draw()
        self.win.withdraw()

        self.cv.bind("<Enter>", lambda e: self._set_hover(True))
        self.cv.bind("<Leave>", lambda e: self._set_hover(False))
        self.cv.bind("<Button-1>", self._drag_start)
        self.cv.bind("<B1-Motion>", self._drag_move)
        self._drag_off = (0, 0)

    # ---------- 基础工具 ----------

    def s(self, v):
        return int(round(v * self._scale))

    def _detect_scale(self):
        try:
            return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
        except Exception:
            return 1.0

    def _place_window(self):
        self.win.update_idletasks()
        pos = self.cfg.get("float_pos")
        if pos and isinstance(pos, (list, tuple)) and len(pos) == 2:
            x, y = int(pos[0]), int(pos[1])
        else:
            sw = self.win.winfo_screenwidth()
            sh = self.win.winfo_screenheight()
            x = (sw - self.s(self.W)) // 2
            y = sh - self.s(self.H) - self.s(110)
        x = max(0, min(x, self.win.winfo_screenwidth() - self.s(self.W)))
        y = max(0, min(y, self.win.winfo_screenheight() - self.s(self.H)))
        self.win.geometry(f"+{x}+{y}")

    def _make_noactivate(self):
        """不抢焦点：否则悬浮条一出现就把键盘焦点从目标窗口夺走。"""
        try:
            self.win.update_idletasks()
            hwnd = int(self.win.winfo_id())
            parent = ctypes.windll.user32.GetParent(hwnd)
            self.hwnd = parent or hwnd
            style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(
                self.hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            )
        except Exception as e:
            self._log(f"设置无焦点样式失败: {e}")

    def hwnd_of(self, widget):
        try:
            return int(widget.winfo_id())
        except Exception:
            return 0

    # ---------- 绘制 ----------

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.cv.create_polygon(pts, smooth=True, **kw)

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W, H = self.s(self.W), self.s(self.H)
        r = self.s(14)

        self._round_rect(1, 1, W - 1, H - 1, r, fill=BG, outline=BORDER, width=1)

        # 播放 / 暂停
        cx, cy, br = self.s(36), self.s(46), self.s(19)
        cv.create_oval(
            cx - br, cy - br, cx + br, cy + br,
            fill=ACCENT, outline="", tags=("play_btn",),
        )
        self._play_icon = (cx, cy)

        # 停止
        sx, sy, sr = self.s(86), self.s(46), self.s(19)
        cv.create_oval(
            sx - sr, sy - sr, sx + sr, sy + sr,
            fill="", outline=BORDER, width=1, tags=("stop_btn",),
        )
        stop_box = self.s(6)
        cv.create_rectangle(
            sx - stop_box, sy - stop_box, sx + stop_box, sy + stop_box,
            fill=SUBTLE, outline="", tags=("stop_btn",),
        )

        # 文本预览
        cv.create_text(
            self.s(120), self.s(28),
            text="", anchor="w", fill=TXT,
            font=self.f_preview, tags=("preview",),
        )

        # 进度条
        px1, px2, py = self.s(120), W - self.s(20), self.s(52)
        cv.create_line(px1, py, px2, py, fill=TRACK, width=self.s(4), capstyle="round")
        self.cv_progress = cv.create_line(
            px1, py, px1, py, fill=ACCENT, width=self.s(4), capstyle="round"
        )

        # 底部：语速 / 音色 / 进度计数
        by = self.s(74)
        font_s = self.f_small
        cv.create_text(self.s(120), by, text="-", anchor="w", fill=SUBTLE,
                       font=font_s, tags=("rate_down",))
        self.cv_rate = cv.create_text(
            self.s(140), by, text="0%", anchor="w", fill=TXT, font=font_s
        )
        cv.create_text(self.s(176), by, text="+", anchor="w", fill=SUBTLE,
                       font=font_s, tags=("rate_up",))
        cv.create_line(self.s(196), by - self.s(6), self.s(196), by + self.s(6),
                       fill=BORDER, width=1)

        self.cv_voice = cv.create_text(
            self.s(212), by, text="晓晓", anchor="w", fill=TXT, font=font_s,
            tags=("voice",),
        )
        self.cv_count = cv.create_text(
            W - self.s(20), by, text="", anchor="e", fill=SUBTLE, font=font_s
        )

        # 交互绑定
        cv.tag_bind("play_btn", "<Button-1>", lambda e: self.cb["toggle_pause"]())
        cv.tag_bind("stop_btn", "<Button-1>", lambda e: self.cb["stop"]())
        cv.tag_bind("rate_down", "<Button-1>", lambda e: self.cb["rate"](-10))
        cv.tag_bind("rate_up", "<Button-1>", lambda e: self.cb["rate"](10))
        cv.tag_bind("voice", "<Button-1>", self._pick_voice)

        for tag in ("play_btn", "stop_btn", "rate_down", "rate_up", "voice"):
            cv.tag_bind(tag, "<Enter>", lambda e: self._set_hover(True))
            cv.tag_bind(tag, "<Leave>", lambda e: self._set_hover(False))

        self._draw_play_icon(False)
        self._sync_voice_label()

    def _draw_play_icon(self, paused: bool):
        cv = self.cv
        cv.delete("play_icon")
        cx, cy = self._play_icon
        if paused:  # 暂停状态 -> 显示播放三角
            a = self.s(8)
            cv.create_polygon(
                cx - a + 2, cy - a, cx - a + 2, cy + a, cx + a + 2, cy,
                fill="#ffffff", outline="", tags=("play_icon",), smooth=False,
            )
        else:  # 正在播 -> 显示暂停双竖线
            w = self.s(3)
            g = self.s(4)
            cv.create_rectangle(cx - g - w, cy - self.s(8), cx - g, cy + self.s(8),
                                fill="#ffffff", outline="", tags=("play_icon",))
            cv.create_rectangle(cx + g, cy - self.s(8), cx + g + w, cy + self.s(8),
                                fill="#ffffff", outline="", tags=("play_icon",))

    def _set_hover(self, on: bool):
        self._hover = on
        if on:
            self._cancel_hide()

    def _sync_voice_label(self):
        voice = self.cfg.get("voice", "")
        name = "晓晓"
        for vid, label in DEFAULT_VOICES:
            if vid == voice:
                name = label.split(" · ")[0]
                break
        self.cv.itemconfigure(self.cv_voice, text=name)
        self.cv.itemconfigure(self.cv_rate, text=f"{int(self.cfg.get('rate', 0)):+d}%")

    # ---------- 音色菜单 ----------

    def _pick_voice(self, _event=None):
        menu = tk.Menu(self.win, tearoff=0, bg="#25252c", fg=TXT,
                       activebackground=ACCENT, activeforeground="#fff",
                       bd=0, font=("Microsoft YaHei UI", 9))
        for vid, label in DEFAULT_VOICES:
            menu.add_radiobutton(
                label=label, value=vid,
                variable=tk.StringVar(value=self.cfg.get("voice")),
                command=lambda v=vid: self.cb["voice"](v),
            )
        menu.tk_popup(self.win.winfo_pointerx(), self.win.winfo_pointery())
        return "break"

    # ---------- 拖动 ----------

    def _drag_start(self, e):
        self._drag_off = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e):
        x = e.x_root - self._drag_off[0]
        y = e.y_root - self._drag_off[1]
        self.win.geometry(f"+{x}+{y}")
        self.cfg["float_pos"] = [x, y]

    def contains(self, x: int, y: int) -> bool:
        try:
            if not self.win.winfo_ismapped():
                return False
            bx, by = self.win.winfo_rootx(), self.win.winfo_rooty()
            return (
                bx <= x <= bx + self.win.winfo_width()
                and by <= y <= by + self.win.winfo_height()
            )
        except Exception:
            return False

    # ---------- 显隐 ----------

    def show(self):
        self._cancel_hide()
        if not self.win.winfo_ismapped():
            self.win.deiconify()
            self.win.attributes("-topmost", True)

    def hide(self):
        self.win.withdraw()

    def _cancel_hide(self):
        if self._hide_job:
            self.win.after_cancel(self._hide_job)
            self._hide_job = None

    def schedule_hide(self, delay_ms=1600):
        self._cancel_hide()

        def _do():
            if not self._hover:
                self.hide()

        self._hide_job = self.win.after(delay_ms, _do)

    # ---------- 状态刷新 ----------

    def refresh(self, state: dict):
        if not state.get("speaking"):
            if self.win.winfo_ismapped():
                self.schedule_hide()
            return

        self._cancel_hide()
        self.show()

        if self._last_drawn.get("paused") != state.get("paused"):
            self._draw_play_icon(bool(state.get("paused")))
            self._last_drawn["paused"] = state.get("paused")

        text = state.get("text", "")
        preview = " ".join(text.split())
        avail = self.s(self.W) - self.s(120) - self.s(16)
        if self.f_preview.measure(preview) > avail:
            while preview and self.f_preview.measure(preview + "…") > avail:
                preview = preview[:-1]
            preview = preview.rstrip() + "…"
        self.cv.itemconfigure("preview", text=preview)

        total = state.get("total") or 0
        idx = (state.get("index") or 0) + 1
        if total > 1:
            self.cv.itemconfigure(self.cv_count, text=f"{idx}/{total}")
        else:
            self.cv.itemconfigure(self.cv_count, text="")

        prog = state.get("progress") or 0.0
        W = self.s(self.W)
        px1, px2, py = self.s(120), W - self.s(20), self.s(52)
        end = px1 + (px2 - px1) * max(0.0, min(1.0, prog))
        self.cv.coords(self.cv_progress, px1, py, max(px1 + 1, end), py)

        self._sync_voice_label()
