"""SelectSpeak 入口。

选中任意文字 -> 自动朗读。
"""
import ctypes
import os
import sys
import time
import tkinter as tk

from config import APP_VERSION, Config, LOG_PATH
from selection import SelectionWatcher
from speech import SpeechPipeline
from ui_bar import FloatBar
from ui_tray import Tray

def make_logger():
    def log(*args):
        line = "[{}] {}".format(time.strftime("%H:%M:%S"), " ".join(str(a) for a in args))
        try:
            print(line)
        except Exception:
            pass
        try:
            if LOG_PATH.exists() and LOG_PATH.stat().st_size > 512 * 1024:
                LOG_PATH.unlink()
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    return log


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def acquire_single_instance():
    """返回句柄；已有实例时返回 None。"""
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.CreateMutexW(None, False, "Local\\SelectSpeakSingleton")
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            return None
        return handle
    except Exception:
        return True


class App:
    def __init__(self, log):
        self.log = log
        self.cfg = Config()

        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("SelectSpeak")

        self.pipeline = SpeechPipeline(self.cfg, self.log)
        self.pipeline.start(wait=False)

        self.bar = FloatBar(
            self.root,
            self.cfg,
            callbacks={
                "toggle_pause": self.toggle_pause,
                "stop": self.stop_speaking,
                "rate": self.change_rate,
                "voice": self.set_voice,
            },
            logger=self.log,
        )

        self.watcher = SelectionWatcher(
            on_text=self.on_text,
            is_active=lambda: bool(self.cfg.get("enabled", True)),
            ignore_at=lambda x, y: self.bar.contains(x, y),
            config=self.cfg,
            logger=self.log,
        )

        self.tray = Tray(
            self.cfg,
            callbacks={
                "enabled": self.set_enabled,
                "rate": self.change_rate,
                "set_rate": self.set_rate,
                "voice": self.set_voice,
                "toggle_bar": self.toggle_bar,
                "stop": self.stop_speaking,
                "quit": self.quit,
            },
            ui_thread=self.root,
            logger=self.log,
        )

        self._err_shown = ""

    # ---------- 启动 ----------

    def run(self):
        self.watcher.start()
        self.tray.start()
        self.root.after(120, self._tick)
        self.root.after(600, self._warmup_check)
        self.log(f"SelectSpeak v{APP_VERSION} 已启动")
        self.root.mainloop()

    def _warmup_check(self):
        state = self.pipeline.state()
        if state.get("error"):
            self.tray.notify("语音服务连接异常，划词时可能失败。详见 SelectSpeak.log")
        else:
            self.tray.notify("已就绪：选中任意文字即可朗读")

    # ---------- 轮询 ----------

    def _tick(self):
        try:
            state = self.pipeline.state()
            if self.cfg.get("float_bar", True):
                self.bar.refresh(state)
            elif state.get("speaking"):
                self.bar.hide()

            err = state.get("error") or ""
            if err and err != self._err_shown:
                self._err_shown = err
                self.log("朗读错误:", err)
                self.tray.notify(f"朗读失败：{err[:80]}")
        except Exception as e:
            self.log("tick 异常:", e)
        finally:
            self.root.after(110, self._tick)

    # ---------- 业务回调（全部在主线程） ----------

    def on_text(self, text: str):
        self.log(f"选中 {len(text)} 字: {text[:40]!r}")
        self.pipeline.speak(text)

    def toggle_pause(self):
        self.pipeline.toggle_pause()

    def stop_speaking(self):
        self.pipeline.stop()
        self.bar.schedule_hide(450)

    def change_rate(self, delta: int):
        self.set_rate(int(self.cfg.get("rate", 0)) + delta)

    def set_rate(self, value: int):
        value = max(-50, min(100, int(value)))
        self.cfg["rate"] = value
        self.cfg.save()
        self.log(f"语速 -> {value:+d}%")

    def set_voice(self, voice: str):
        if voice:
            self.cfg["voice"] = voice
            self.cfg.save()
            self.log(f"音色 -> {voice}")

    def set_enabled(self, enabled: bool):
        self.cfg["enabled"] = bool(enabled)
        self.cfg.save()
        self.tray.icon.update_menu()
        if not enabled:
            self.pipeline.stop()
        self.tray.notify("划词朗读已启用" if enabled else "划词朗读已暂停")

    def toggle_bar(self, show: bool):
        self.cfg["float_bar"] = bool(show)
        self.cfg.save()
        self.tray.icon.update_menu()
        if not show:
            self.bar.hide()

    def quit(self):
        self.log("正在退出")
        try:
            self.cfg.save()
        except Exception:
            pass
        try:
            self.watcher.stop()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.pipeline.shutdown()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)


def main():
    log = make_logger()
    handle = acquire_single_instance()
    if handle is None:
        log("已有实例在运行，退出")
        try:
            ctypes.windll.user32.MessageBoxW(
                0, "SelectSpeak 已经在运行了（看右下角托盘）。", "SelectSpeak", 0x40
            )
        except Exception:
            pass
        sys.exit(0)

    set_dpi_aware()
    app = App(log)
    app.run()


if __name__ == "__main__":
    main()
