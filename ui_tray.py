"""托盘图标 + 右键菜单。"""
import threading

import pystray
from PIL import Image, ImageDraw

from config import DEFAULT_VOICES

ACCENT = (76, 141, 255, 255)


def make_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(size * 0.28)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=ACCENT)
    u = size / 64.0

    def S(v):
        return int(round(v * u))

    # 喇叭本体
    d.rectangle([S(15), S(26), S(21), S(38)], fill=(255, 255, 255, 255))
    d.polygon(
        [(S(21), S(26)), (S(31), S(16)), (S(31), S(48)), (S(21), S(38))],
        fill=(255, 255, 255, 255),
    )
    # 声波
    d.arc([S(30), S(22), S(44), S(42)], start=-55, end=55,
          fill=(255, 255, 255, 255), width=S(3))
    d.arc([S(28), S(14), S(52), S(50)], start=-50, end=50,
          fill=(255, 255, 255, 190), width=S(2.5))
    return img


class Tray:
    def __init__(self, config, callbacks: dict, ui_thread, logger=None):
        """callbacks: enabled(bool), rate(int delta), voice(str), toggle_bar(bool),
        reload_voices(), quit()
        ui_thread: 主线程的 root，用于把回调转回 UI 线程
        """
        self.cfg = config
        self.cb = callbacks
        self.root = ui_thread
        self._log = logger or (lambda *a: None)
        self.icon = pystray.Icon(
            "SelectSpeak",
            make_icon(),
            "SelectSpeak · 划词朗读",
            menu=self._build_menu(),
        )
        self._thread = None

    def _post(self, fn, *args):
        self.root.after(0, lambda: fn(*args))

    def _build_menu(self):
        def voice_items():
            for vid, label in DEFAULT_VOICES:
                yield pystray.MenuItem(
                    label,
                    lambda v=vid: self._post(self.cb["voice"], v),
                    checked=lambda item, v=vid: self.cfg.get("voice") == v,
                    radio=True,
                )

        return pystray.Menu(
            pystray.MenuItem(
                "启用划词朗读",
                lambda: self._post(self.cb["enabled"], not self.cfg.get("enabled", True)),
                checked=lambda item: bool(self.cfg.get("enabled", True)),
            ),
            pystray.MenuItem(
                "显示悬浮条",
                lambda: self._post(self.cb["toggle_bar"],
                                   not self.cfg.get("float_bar", True)),
                checked=lambda item: bool(self.cfg.get("float_bar", True)),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("语速", pystray.Menu(
                pystray.MenuItem("慢一点 (-10%)",
                                 lambda: self._post(self.cb["rate"], -10)),
                pystray.MenuItem("快一点 (+10%)",
                                 lambda: self._post(self.cb["rate"], 10)),
                pystray.MenuItem("恢复默认",
                                 lambda: self._post(self.cb["set_rate"], 0)),
            )),
            pystray.MenuItem("音色", pystray.Menu(voice_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("停止朗读",
                             lambda: self._post(self.cb["stop"])),
            pystray.MenuItem("退出", lambda: self._post(self.cb["quit"])),
        )

    def start(self):
        self._thread = threading.Thread(target=self.icon.run, daemon=True, name="tray")
        self._thread.start()

    def notify(self, msg: str, title: str = "SelectSpeak"):
        try:
            self.icon.notify(msg, title)
        except Exception:
            pass

    def stop(self):
        try:
            self.icon.stop()
        except Exception:
            pass
