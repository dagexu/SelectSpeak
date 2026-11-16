"""Edge TTS 引擎。

关键点：微软这个接口允许在同一条 WebSocket 上连续做多轮合成。
握手要 1.2s，单轮合成只要 0.5s，所以这里保持常驻连接，
启动时预热一次，之后每句都能秒出。
"""
import asyncio
import re
import ssl
import threading
import time
import uuid
from xml.sax.saxutils import escape

import aiohttp
import certifi

from edge_tts.communicate import date_to_string, mkssml, ssml_headers_plus_data
from edge_tts.constants import SEC_MS_GEC_VERSION, WSS_HEADERS, WSS_URL
from edge_tts.data_classes import TTSConfig
from edge_tts.drm import DRM

_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

# 连接空闲超过这个时间就主动重连，避免拿到半死的 socket
IDLE_RECONNECT_SEC = 180


class EdgeTTSEngine:
    def __init__(self, logger=None):
        self._log = logger or (lambda *a: None)
        self._loop = None
        self._thread = None
        self._session = None
        self._ws = None
        self._ready = threading.Event()
        self._last_used = 0.0
        self._lock = threading.Lock()

    # ---------- 生命周期 ----------

    def start(self, wait: bool = True):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="tts-engine"
        )
        self._thread.start()
        if wait:
            self._ready.wait(timeout=8)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect())
        except Exception as e:
            self._log(f"预热连接失败: {e}")
        self._ready.set()
        self._loop.run_forever()

    def stop(self):
        if not self._loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._close(), self._loop).result(3)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)

    # ---------- 连接管理 ----------

    async def _connect(self):
        await self._close()
        self._session = aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=30)
        )
        url = (
            f"{WSS_URL}&ConnectionId={uuid.uuid4().hex}"
            f"&Sec-MS-GEC={DRM.generate_sec_ms_gec()}"
            f"&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
        )
        self._ws = await self._session.ws_connect(
            url, compress=15, headers=DRM.headers_with_muid(WSS_HEADERS), ssl=_SSL_CTX
        )
        # 一场会话只需要发一次 config
        await self._ws.send_str(
            f"X-Timestamp:{date_to_string()}\r\n"
            "Content-Type:application/json; charset=utf-8\r\n"
            "Path:speech.config\r\n\r\n"
            '{"context":{"synthesis":{"audio":{"metadataoptions":{'
            '"sentenceBoundaryEnabled":"true","wordBoundaryEnabled":"false"'
            "},"
            '"outputFormat":"audio-24khz-48kbitrate-mono-mp3"'
            "}}}}\r\n"
        )
        self._last_used = time.time()
        self._log("语音服务已连接（常驻）")

    async def _close(self):
        if self._ws is not None and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None
        if self._session is not None:
            try:
                await self._session.close()
            except Exception:
                pass
        self._session = None

    async def _ensure(self):
        stale = self._ws is None or self._ws.closed
        if not stale and time.time() - self._last_used > IDLE_RECONNECT_SEC:
            stale = True
        if stale:
            await self._connect()

    # ---------- 合成 ----------

    async def _synth_once(
        self, text: str, voice: str, rate: str, volume: str = "+0%"
    ) -> bytes:
        await self._ensure()
        cfg = TTSConfig(
            voice=voice,
            rate=rate,
            volume=volume,
            pitch="+0Hz",
            boundary="SentenceBoundary",
        )
        request_id = uuid.uuid4().hex.upper()
        ssml = mkssml(cfg, escape(text))
        await self._ws.send_str(
            ssml_headers_plus_data(request_id, date_to_string(), ssml)
        )

        audio = bytearray()
        while True:
            msg = await self._ws.receive(timeout=25)
            if msg.type == aiohttp.WSMsgType.TEXT:
                if "Path:turn.end" in msg.data:
                    break
            elif msg.type == aiohttp.WSMsgType.BINARY:
                header_len = int.from_bytes(msg.data[:2], "big")
                header = msg.data[2 : 2 + header_len]
                if b"Path:audio" in header:
                    audio += msg.data[2 + header_len :]
            elif msg.type in (
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.ERROR,
            ):
                raise ConnectionError(f"语音连接中断: {msg.type}")
        if not audio:
            raise RuntimeError("未收到音频数据")
        self._last_used = time.time()
        return bytes(audio)

    async def _synth(self, text: str, voice: str, rate: str, volume: str) -> bytes:
        try:
            return await self._synth_once(text, voice, rate, volume)
        except Exception as e:
            # 连接类错误一律重连重试一次
            self._log(f"合成失败，重连重试: {e}")
            self._ws = None
            return await self._synth_once(text, voice, rate, volume)

    def synth(
        self, text: str, voice: str, rate_pct: int = 0, volume_pct: int = 100
    ) -> bytes:
        """同步接口：文本 -> mp3 字节。volume_pct 100 为原始音量。"""
        if not self._loop:
            raise RuntimeError("引擎未启动")
        rate = f"{rate_pct:+d}%"
        vol = f"{max(-100, min(0, int(volume_pct) - 100)):+d}%"
        fut = asyncio.run_coroutine_threadsafe(
            self._synth(text, voice, rate, vol), self._loop
        )
        return fut.result(timeout=30)


# ---------- 文本预处理 ----------

_SENT_SPLIT = re.compile(r"(?<=[。！？!?；;…\n])")
_ABBREV = ("e.g.", "i.e.", "Mr.", "Mrs.", "Dr.", "etc.", "vs.")


def split_sentences(text: str, max_len: int = 120) -> list:
    """按句切分，保证每段不超过 max_len，便于流水线播放。"""
    text = re.sub(r"[ \t]+", " ", text).strip()
    parts = []
    for raw in _SENT_SPLIT.split(text):
        raw = raw.strip()
        if not raw:
            continue
        # 超长句按逗号再切
        if len(raw) > max_len:
            buf = ""
            for piece in re.split(r"(?<=[，,、：:])", raw):
                if len(buf) + len(piece) > max_len and buf:
                    parts.append(buf)
                    buf = piece
                else:
                    buf += piece
            if buf.strip():
                parts.append(buf.strip())
        else:
            parts.append(raw)
    return parts or ([text.strip()] if text.strip() else [])
