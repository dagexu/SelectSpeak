"""朗读流水线：分句合成 + 双缓冲播放。

一句在播的时候，下一句已经在合成了，所以句与句之间不会有 0.5s 的空档。
"""
import queue
import shutil
import tempfile
import threading
import time
from pathlib import Path

from player import MciPlayer
from tts_engine import EdgeTTSEngine, split_sentences


class SpeechPipeline:
    def __init__(self, config, logger=None):
        self.cfg = config
        self._log = logger or (lambda *a: None)
        self.engine = EdgeTTSEngine(logger=self._log)
        self.player = MciPlayer()
        self._tmpdir = Path(tempfile.mkdtemp(prefix="selectspeak_"))
        self._cancel = threading.Event()
        self._thread = None
        self._mci_lock = threading.Lock()
        self._paused = threading.Event()
        self._state_lock = threading.Lock()
        self._state = {
            "speaking": False,
            "paused": False,
            "text": "",
            "index": 0,
            "total": 0,
            "progress": 0.0,
            "error": "",
        }

    # ---------- 状态 ----------

    def state(self) -> dict:
        with self._state_lock:
            return dict(self._state)

    def _update(self, **kw):
        with self._state_lock:
            self._state.update(kw)

    # ---------- 生命周期 ----------

    def start(self, wait: bool = False):
        self.engine.start(wait=wait)

    def shutdown(self):
        self.stop(wait=True)
        try:
            self.engine.stop()
        except Exception:
            pass
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ---------- 控制 ----------

    def speak(self, text: str):
        text = (text or "").strip()
        if not text:
            return
        self.stop(wait=True)
        self._cancel = threading.Event()
        self._paused.clear()
        self._update(
            speaking=True, paused=False, text=text, index=0, total=0, progress=0.0, error=""
        )
        self._thread = threading.Thread(target=self._run, args=(text,), daemon=True)
        self._thread.start()

    def stop(self, wait: bool = False):
        self._cancel.set()
        self._paused.clear()
        with self._mci_lock:
            try:
                self.player.stop()
            except Exception:
                pass
        if wait and self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._update(speaking=False, paused=False, progress=0.0)

    def toggle_pause(self):
        if self._paused.is_set():
            self._paused.clear()
            self._update(paused=False)
        else:
            if self._state.get("speaking"):
                self._paused.set()
                self._update(paused=True)

    # ---------- 主流程 ----------

    def _run(self, text: str):
        cancel = self._cancel
        try:
            sentences = split_sentences(text)
            total = len(sentences)
            self._update(total=total)
            if total == 0:
                return

            buffer = queue.Queue(maxsize=2)
            err_box = []

            def producer():
                for i, sent in enumerate(sentences):
                    if cancel.is_set():
                        break
                    try:
                        audio = self.engine.synth(
                            sent,
                            self.cfg["voice"],
                            int(self.cfg["rate"]),
                            int(self.cfg.get("volume", 100)),
                        )
                    except Exception as e:
                        err_box.append(str(e))
                        break
                    if cancel.is_set():
                        break
                    buffer.put((i, audio))
                buffer.put(None)

            threading.Thread(target=producer, daemon=True).start()

            while True:
                item = buffer.get()
                if item is None or cancel.is_set():
                    break
                index, audio = item
                path = self._tmpdir / f"seg_{index % 4}.mp3"
                try:
                    path.write_bytes(audio)
                except Exception as e:
                    err_box.append(f"写临时文件失败: {e}")
                    break

                self._update(index=index, progress=0.0)
                with self._mci_lock:
                    try:
                        self.player.open(str(path))
                        self.player.play()
                    except Exception as e:
                        err_box.append(f"播放失败: {e}")
                        break

                self._wait_segment_done(cancel)

            if err_box:
                self._update(error=err_box[0])
                self._log(f"朗读出错: {err_box[0]}")
        except Exception as e:
            self._update(error=str(e))
            self._log(f"流水线异常: {e}")
        finally:
            with self._mci_lock:
                try:
                    self.player.close()
                except Exception:
                    pass
            self._update(speaking=False, paused=False, progress=0.0)

    def _wait_segment_done(self, cancel):
        while True:
            if cancel.is_set():
                with self._mci_lock:
                    self.player.stop()
                return

            if self._paused.is_set():
                with self._mci_lock:
                    self.player.pause()
                while self._paused.is_set() and not cancel.is_set():
                    time.sleep(0.06)
                with self._mci_lock:
                    self.player.resume()
                if cancel.is_set():
                    return

            with self._mci_lock:
                mode = self.player.mode
                length = self.player.length_ms
                pos = self.player.position_ms
            if length > 0:
                self._update(progress=min(1.0, pos / length))
            if mode == "stopped":
                return
            time.sleep(0.06)
