"""全局鼠标监听 + 抓取当前选中的文字。

思路：鼠标松开后，先备份剪贴板，再模拟复制快捷键，看剪贴板序列号有没有变化。
序列号变了 = 确实有选中内容被复制出来；没变 = 没选中，什么都不做。
读完把原剪贴板还原回去。

默认用 Ctrl+Insert 而不是 Ctrl+C —— 终端里 Ctrl+C 是中断信号，
选中文字后触发中断会很烦。Ctrl+Insert 几乎所有 Windows 程序都支持复制。
"""
import ctypes
import hashlib
import threading
import time

import win32clipboard
import win32con
from pynput import keyboard, mouse

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetClipboardSequenceNumber.restype = ctypes.c_ulong
_user32.GetForegroundWindow.restype = ctypes.c_void_p
_user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]

# 这些窗口里 Ctrl+C 有副作用，兜底时不要用
TERMINAL_CLASSES = {
    "ConsoleWindowClass",
    "CASCADIA_HOSTING_WINDOW_CLASS",
    "Windows.UI.Core.CoreWindow",
    "mintty",
}


def get_clipboard_text(retries: int = 6):
    for _ in range(retries):
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.015)
    return None


def set_clipboard_text(text: str) -> bool:
    for _ in range(6):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.015)
    return False


def foreground_class() -> str:
    try:
        hwnd = _user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        _user32.GetClassNameW(hwnd, buf, 256)
        return buf.value
    except Exception:
        return ""


class SelectionWatcher:
    def __init__(self, on_text, is_active, config, ignore_at=None, logger=None):
        """on_text(str)：拿到选中文本后的回调
        is_active() -> bool：当前是否处于启用状态
        ignore_at(x, y) -> bool：这个坐标上松手是否需要忽略（比如自家悬浮条）
        """
        self.on_text = on_text
        self.is_active = is_active
        self.ignore_at = ignore_at
        self.cfg = config
        self._log = logger or (lambda *a: None)

        self._listener = None
        self._kb = keyboard.Controller()
        self._press_pos = (0, 0)
        self._press_time = 0.0
        self._click_count = 0
        self._last_text = ""
        self._last_text_at = 0.0
        self._busy = threading.Lock()
        self._gen = 0
        self._self_hwnds = set()

    # ---------- 对外 ----------

    def start(self):
        self._listener = mouse.Listener(on_click=self._on_click)
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        if self._listener:
            self._listener.stop()

    def ignore_window(self, hwnd: int):
        """注册自家窗口，在这些窗口上松手不触发。"""
        if hwnd:
            self._self_hwnds.add(int(hwnd))

    # ---------- 鼠标事件 ----------

    def _on_click(self, x, y, button, pressed):
        if button != mouse.Button.left:
            return
        if not pressed:
            self._on_release(x, y)
            return

        now = time.time()
        dx = abs(x - self._press_pos[0])
        dy = abs(y - self._press_pos[1])
        if now - self._press_time < 0.45 and max(dx, dy) < 6:
            self._click_count += 1
        else:
            self._click_count = 1
        self._press_pos = (x, y)
        self._press_time = now
        # 新的按下会作废之前挂起的抓取
        self._gen += 1

    def _on_release(self, x, y):
        if self.ignore_at and self.ignore_at(x, y):
            return
        moved = max(abs(x - self._press_pos[0]), abs(y - self._press_pos[1])) > 6
        multi = self._click_count >= 2

        # 单击不处理：避免在终端里乱发快捷键
        if not moved and not multi:
            return
        if not self.is_active():
            return

        gen = self._gen
        delay = 0.16 if multi else 0.06
        threading.Thread(
            target=self._grab_later, args=(gen, delay), daemon=True
        ).start()

    # ---------- 抓取 ----------

    def _grab_later(self, gen: int, delay: float):
        time.sleep(delay)
        if gen != self._gen:  # 期间又点了一次，让新的那次去处理
            return
        if not self._busy.acquire(blocking=False):
            return
        try:
            text = self._grab()
            if not text:
                return
            text = text.strip()
            if len(text) < int(self.cfg.get("min_chars", 1)):
                return
            now = time.time()
            digest = hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()
            if digest == self._last_text and now - self._last_text_at < 1.5:
                return
            self._last_text = digest
            self._last_text_at = now
            self.on_text(text[: int(self.cfg.get("max_chars", 3000))])
        except Exception as e:
            self._log(f"抓取选中文字失败: {e}")
        finally:
            self._busy.release()

    def _grab(self):
        old_text = get_clipboard_text()
        seq0 = _user32.GetClipboardSequenceNumber()

        self._send_copy()

        changed = False
        for _ in range(28):
            time.sleep(0.012)
            if _user32.GetClipboardSequenceNumber() != seq0:
                changed = True
                break

        if not changed:
            # Ctrl+Insert 没被响应，非终端窗口再试一次 Ctrl+C
            if self.cfg.get("copy_key") == "insert":
                if foreground_class() not in TERMINAL_CLASSES:
                    seq0 = _user32.GetClipboardSequenceNumber()
                    self._send_copy(force_ctrl_c=True)
                    for _ in range(28):
                        time.sleep(0.012)
                        if _user32.GetClipboardSequenceNumber() != seq0:
                            changed = True
                            break
            if not changed:
                return None

        text = get_clipboard_text()
        if old_text:
            set_clipboard_text(old_text)
        return text

    def _send_copy(self, force_ctrl_c: bool = False):
        use_ctrl_c = force_ctrl_c or self.cfg.get("copy_key") == "ctrl_c"
        key = (
            keyboard.KeyCode.from_char("c")
            if use_ctrl_c
            else keyboard.Key.insert
        )
        try:
            self._kb.press(keyboard.Key.ctrl_l)
            time.sleep(0.012)
            self._kb.press(key)
            time.sleep(0.012)
            self._kb.release(key)
            time.sleep(0.012)
            self._kb.release(keyboard.Key.ctrl_l)
        except Exception as e:
            self._log(f"发送复制快捷键失败: {e}")
