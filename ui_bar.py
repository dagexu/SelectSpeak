"""悬浮控制条：无边框、置顶、不抢焦点，全部 Canvas 自绘。

视觉原则：
- 只保留一个视觉重心（蓝色播放键），其余元素压低对比度
- 三层信息：正文 / 进度 / 次要控件，行距留足
- 消失走淡出，不做硬切
"""
import ctypes
import tkinter as tk
import tkinter.font as tkfont

from config import DEFAULT_VOICES

BG = "#1A1A20"
BORDER = "#2E2E38"
TXT = "#ECECF1"
CTRL = "#B9B9C4"
SUBTLE = "#8B8B97"
DIM = "#5E5E6A"
ACCENT = "#4C8DFF"
ACCENT_HI = "#6BA2FF"
TRACK = "#2B2B34"
HOVER = "#25252D"
WHITE = "#FFFFFF"
KEYCOLOR = "#010203"

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080


class FloatBar:
    W, H = 560, 96

    FADE_STEPS = 5
    FADE_INTERVAL = 24  # ms，5 × 24 ≈ 120ms 淡出

    def __init__(self, root: tk.Tk, config, callbacks: dict, logger=None):
        self.root = root
        self.cfg = config
        self.cb = callbacks
        self._log = logger or (lambda *a: None)
        self._scale = self._detect_scale()
        self._hide_job = None
        self._fade_job = None
        self._hover = False
        self._speaking = False
        self._last_drawn = {}

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=KEYCOLOR)
        try:
            self.win.attributes("-transparentcolor", KEYCOLOR)
        except Exception:
            pass

        self.f_text = tkfont.Font(
            family="Microsoft YaHei UI", size=max(9, self.s(11))
        )
        self.f_meta = tkfont.Font(
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
            y = sh - self.s(self.H) - self.s(120)
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

        # 卡片
        self._round_rect(1, 1, W - 1, H - 1, self.s(20), fill=BG, outline=BORDER, width=1)
        # 顶部一道极细的高光，制造玻璃边缘的厚度感
        cv.create_line(
            self.s(22), self.s(2), W - self.s(22), self.s(2),
            fill="#33333E", width=1,
        )

        # 主按钮：播放 / 暂停
        cx, cy, br = self.s(42), self.s(48), self.s(22)
        self._play_center = (cx, cy)
        cv.create_oval(
            cx - br, cy - br, cx + br, cy + br,
            fill=ACCENT, outline="", tags=("play_btn",),
        )
        # 主按钮外圈微光（静止时不可见，hover 时换成亮色）
        cv.create_oval(
            cx - br - 1, cy - br - 1, cx + br + 1, cy + br + 1,
            fill="", outline="", width=1, tags=("play_ring",),
        )

        # 次要按钮：停止
        sx, sy, sr = self.s(100), self.s(48), self.s(16)
        cv.create_oval(
            sx - sr, sy - sr, sx + sr, sy + sr,
            fill="", outline="#3A3A46", width=1, tags=("stop_btn",),
        )
        sb = self.s(6)
        self._round_rect(
            sx - sb, sy - sb, sx + sb, sy + sb, self.s(3),
            fill="#B4B4BF", outline="", tags=("stop_btn",),
        )

        # 正文
        cv.create_text(
            self.s(136), self.s(31),
            text="", anchor="w", fill=TXT,
            font=self.f_text, tags=("preview",),
        )

        # 进度
        px1, px2, py = self.s(136), W - self.s(26), self.s(52)
        self._prog = (px1, px2, py)
        cv.create_line(px1, py, px2, py, fill=TRACK, width=self.s(4), capstyle="round")
        self.cv_progress = cv.create_line(
            px1, py, px1, py, fill=ACCENT, width=self.s(4), capstyle="round"
        )

        # 次要控件行
        my = self.s(75)
        f = self.f_meta

        def hover_bg(x1, y1, x2, y2, tag):
            rid = self._round_rect(x1, y1, x2, y2, self.s(7), fill=BG, outline="", tags=(tag,))
            cv.tag_bind(tag, "<Enter>", lambda e, r=rid: cv.itemconfigure(r, fill=HOVER))
            cv.tag_bind(tag, "<Leave>", lambda e, r=rid: cv.itemconfigure(r, fill=BG))
            return rid

        # 语速
        hover_bg(self.s(128), self.s(59), self.s(156), self.s(91), "hb_down")
        cv.create_text(self.s(142), my, text="-", fill=DIM, font=f, tags=("rate_down",))
        self.cv_rate = cv.create_text(
            self.s(169), my, text="0%", anchor="center", fill=CTRL, font=f
        )
        hover_bg(self.s(182), self.s(59), self.s(210), self.s(91), "hb_up")
        cv.create_text(self.s(196), my, text="+", fill=DIM, font=f, tags=("rate_up",))

        cv.create_line(
            self.s(224), self.s(65), self.s(224), self.s(85), fill=BORDER, width=1
        )

        # 音色
        hover_bg(self.s(232), self.s(59), self.s(320), self.s(91), "hb_voice")
        self._voice_x = self.s(240)
        self.cv_voice = cv.create_text(
            self._voice_x, my, text="晓晓", anchor="w", fill=CTRL, font=f,
            tags=("voice",),
        )
        self.cv_chev = cv.create_line(
            0, 0, 0, 0, fill=DIM, width=max(1, self.s(1)),
            capstyle="round", joinstyle="round", tags=("voice",),
        )

        # 句数
        self.cv_count = cv.create_text(
            W - self.s(26), my, text="", anchor="e", fill=DIM, font=f
        )

        # 交互
        cv.tag_bind("play_btn", "<Button-1>", self._on_play)
        cv.tag_bind("stop_btn", "<Button-1>", self._on_stop)
        cv.tag_bind("rate_down", "<Button-1>", self._on_rate_down)
        cv.tag_bind("rate_up", "<Button-1>", self._on_rate_up)
        cv.tag_bind("voice", "<Button-1>", self._pick_voice)
        cv.tag_bind("hb_down", "<Button-1>", self._on_rate_down)
        cv.tag_bind("hb_up", "<Button-1>", self._on_rate_up)
        cv.tag_bind("hb_voice", "<Button-1>", self._pick_voice)

        for tag in ("play_btn", "stop_btn"):
            cv.tag_bind(tag, "<Enter>", lambda e: self._set_hover(True))
        cv.tag_bind("play_btn", "<Enter>", lambda e: cv.itemconfigure("play_btn", fill=ACCENT_HI))
        cv.tag_bind("play_btn", "<Leave>", lambda e: cv.itemconfigure("play_btn", fill=ACCENT))

        self._draw_play_icon(False)
        self._sync_voice_label()

    def _draw_play_icon(self, paused: bool):
        cv = self.cv
        cv.delete("play_icon")
        cx, cy = self._play_center
        if paused:  # 暂停中 -> 显示播放三角
            a = self.s(8)
            cv.create_polygon(
                cx - a + self.s(2), cy - a,
                cx - a + self.s(2), cy + a,
                cx + a + self.s(3), cy,
                fill=WHITE, outline="", tags=("play_icon",),
            )
        else:  # 正在播 -> 显示暂停双竖线
            w = self.s(3)
            g = self.s(4)
            cv.create_rectangle(
                cx - g - w, cy - self.s(9), cx - g, cy + self.s(9),
                fill=WHITE, outline="", tags=("play_icon",),
            )
            cv.create_rectangle(
                cx + g, cy - self.s(9), cx + g + w, cy + self.s(9),
                fill=WHITE, outline="", tags=("play_icon",),
            )

    # ---------- 事件 ----------

    def _on_play(self, _event=None):
        self.cb["toggle_pause"]()
        return "break"

    def _on_stop(self, _event=None):
        self.cb["stop"]()
        return "break"

    def _on_rate_down(self, _event=None):
        self.cb["rate"](-10)
        return "break"

    def _on_rate_up(self, _event=None):
        self.cb["rate"](10)
        return "break"

    def _set_hover(self, on: bool):
        self._hover = on
        if on:
            self._cancel_hide()
        else:
            self._settle()

    def _settle(self):
        """鼠标离开后：若已不在条内且未朗读，安排在 400ms 后收起。"""
        if not self._hover and not self._speaking and self.win.winfo_ismapped():
            self.schedule_hide(400)

    def _sync_voice_label(self):
        voice = self.cfg.get("voice", "")
        name = "晓晓"
        for vid, label in DEFAULT_VOICES:
            if vid == voice:
                name = label.split(" · ")[0]
                break
        self.cv.itemconfigure(self.cv_voice, text=name)
        rate = int(self.cfg.get("rate", 0))
        self.cv.itemconfigure(self.cv_rate, text="0%" if rate == 0 else f"{rate:+d}%")
        # 下拉小箭头：用线段画，跟着文字宽度走
        x = self._voice_x + self.f_meta.measure(name) + self.s(8)
        y = self.s(75)
        d = self.s(3)
        self.cv.coords(
            self.cv_chev, x - d, y - self.s(2), x, y + self.s(2), x + d, y - self.s(2)
        )

    # ---------- 音色菜单 ----------

    def _pick_voice(self, _event=None):
        menu = tk.Menu(self.win, tearoff=0, bg="#25252C", fg=TXT,
                       activebackground=ACCENT, activeforeground=WHITE,
                       bd=0, font=("Microsoft YaHei UI", 9))
        var = tk.StringVar(value=self.cfg.get("voice"))
        for vid, label in DEFAULT_VOICES:
            menu.add_radiobutton(
                label=label, value=vid, variable=var,
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
        self._cancel_fade()
        if not self.win.winfo_ismapped():
            try:
                self.win.attributes("-alpha", 1.0)
            except Exception:
                pass
            self.win.deiconify()
            self.win.attributes("-topmost", True)

    def hide(self, animate: bool = True):
        self._cancel_hide()
        self._cancel_fade()
        if not self.win.winfo_ismapped():
            return
        if not animate:
            self.win.withdraw()
            return
        self._fade(1)

    def _cancel_fade(self):
        if self._fade_job:
            try:
                self.win.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None

    def _fade(self, step: int):
        self._fade_job = None
        if step > self.FADE_STEPS:
            self.win.withdraw()
            try:
                self.win.attributes("-alpha", 1.0)
            except Exception:
                pass
            return
        alpha = 1.0 - step / float(self.FADE_STEPS)
        try:
            self.win.attributes("-alpha", max(0.08, alpha))
        except Exception:
            self.win.withdraw()
            return
        self._fade_job = self.win.after(
            self.FADE_INTERVAL, lambda: self._fade(step + 1)
        )

    def _cancel_hide(self):
        if self._hide_job:
            try:
                self.win.after_cancel(self._hide_job)
            except Exception:
                pass
            self._hide_job = None

    def schedule_hide(self, delay_ms: int = 500):
        """播放结束后 500ms 收起，加 120ms 淡出，总体在 0.8s 内消失。"""
        self._cancel_hide()

        def _do():
            self._hide_job = None
            if not self._hover:
                self.hide()

        self._hide_job = self.win.after(delay_ms, _do)

    # ---------- 状态刷新 ----------

    def refresh(self, state: dict):
        self._speaking = bool(state.get("speaking"))

        if not self._speaking:
            if self.win.winfo_ismapped() and self._hide_job is None and self._fade_job is None:
                self.schedule_hide()
            return

        self._cancel_hide()
        self.show()

        if self._last_drawn.get("paused") != state.get("paused"):
            self._draw_play_icon(bool(state.get("paused")))
            self._last_drawn["paused"] = state.get("paused")

        text = state.get("text", "")
        preview = " ".join(text.split())
        px1, px2, _py = self._prog
        avail = px2 - px1
        if self.f_text.measure(preview) > avail:
            while preview and self.f_text.measure(preview + "…") > avail:
                preview = preview[:-1]
            preview = preview.rstrip() + "…"
        self.cv.itemconfigure("preview", text=preview)

        total = state.get("total") or 0
        idx = (state.get("index") or 0) + 1
        if total > 1:
            self.cv.itemconfigure(self.cv_count, text=f"{idx} / {total}")
        else:
            self.cv.itemconfigure(self.cv_count, text="")

        prog = state.get("progress") or 0.0
        end = px1 + (px2 - px1) * max(0.0, min(1.0, prog))
        self.cv.coords(self.cv_progress, px1, _py, max(px1 + 1, end), _py)

        self._sync_voice_label()
