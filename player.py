"""基于 Windows MCI (winmm.dll) 的 mp3 播放器。

选 MCI 的原因：系统自带、零依赖、支持 mp3、支持暂停/续播/进度查询，
打包体积比 pygame / sounddevice 小得多。
"""
import ctypes
import os

_winmm = ctypes.WinDLL("winmm.dll")


class MciError(RuntimeError):
    pass


class MciPlayer:
    def __init__(self, alias: str = "ssplayer"):
        self.alias = alias
        self._opened = False

    # ---------- 底层 ----------

    def _cmd(self, cmd: str, want_result: bool = False) -> str:
        buf = ctypes.create_unicode_buffer(512)
        err = _winmm.mciSendStringW(
            cmd, buf if want_result else None, 512 if want_result else 0, 0
        )
        if err:
            ebuf = ctypes.create_unicode_buffer(512)
            _winmm.mciGetErrorStringW(err, ebuf, 512)
            raise MciError(f"[{err}] {ebuf.value} :: {cmd}")
        return buf.value

    # ---------- 控制 ----------

    def open(self, path: str):
        self.close()
        p = os.path.abspath(path)
        try:
            self._cmd(f'open "{p}" type mpegvideo alias {self.alias}')
        except MciError:
            self._cmd(f'open "{p}" alias {self.alias}')
        self._opened = True
        self._cmd(f"set {self.alias} time format milliseconds")

    def play(self):
        self._cmd(f"play {self.alias}")

    def pause(self):
        try:
            self._cmd(f"pause {self.alias}")
        except MciError:
            pass

    def resume(self):
        try:
            self._cmd(f"resume {self.alias}")
        except MciError:
            pass

    def stop(self):
        try:
            self._cmd(f"stop {self.alias}")
        except MciError:
            pass

    def close(self):
        if self._opened:
            try:
                self._cmd(f"close {self.alias}")
            except MciError:
                pass
            self._opened = False

    # ---------- 状态 ----------

    def status(self, what: str, default=None):
        if not self._opened:
            return default
        try:
            return self._cmd(f"status {self.alias} {what}", want_result=True)
        except MciError:
            return default

    @property
    def mode(self) -> str:
        """playing / paused / stopped / '' """
        return self.status("mode", "") or ""

    @property
    def length_ms(self) -> int:
        try:
            return int(self.status("length", "0") or 0)
        except ValueError:
            return 0

    @property
    def position_ms(self) -> int:
        try:
            return int(self.status("position", "0") or 0)
        except ValueError:
            return 0

    def seek(self, ms: int):
        try:
            self._cmd(f"seek {self.alias} to {max(0, int(ms))}")
        except MciError:
            pass


def list_voices_hint():
    """调试用：返回系统 SAPI 语音名，便于排查。"""
    try:
        import win32com.client

        v = win32com.client.Dispatch("SAPI.SpVoice")
        return [t.GetDescription() for t in v.GetVoices()]
    except Exception:
        return []
