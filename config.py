"""配置读写。配置放在 exe 同目录的 config.json。"""
import json
import os
import sys
from pathlib import Path

APP_NAME = "SelectSpeak"
APP_VERSION = "1.1.0"

DEFAULT_VOICES = [
    ("zh-CN-XiaoxiaoNeural", "晓晓 · 女声 · 温柔自然"),
    ("zh-CN-XiaoyiNeural", "晓伊 · 女声 · 活泼"),
    ("zh-CN-YunxiNeural", "云希 · 男声 · 年轻"),
    ("zh-CN-YunjianNeural", "云健 · 男声 · 浑厚"),
    ("zh-CN-YunyangNeural", "云扬 · 男声 · 播音腔"),
    ("zh-CN-liaoning-XiaobeiNeural", "晓北 · 女声 · 东北话"),
    ("zh-CN-shaanxi-XiaoniNeural", "晓妮 · 女声 · 陕西话"),
    ("zh-HK-HiuMaanNeural", "曉曼 · 女声 · 粤语"),
    ("zh-TW-HsiaoChenNeural", "曉臻 · 女声 · 台湾腔"),
    ("en-US-AriaNeural", "Aria · 英文女声"),
    ("en-US-GuyNeural", "Guy · 英文男声"),
]

DEFAULTS = {
    "enabled": True,
    "voice": "zh-CN-XiaoxiaoNeural",
    "rate": 0,            # 语速偏移百分比 -50 ~ +100
    "volume": 100,        # 0 ~ 100，MCI 不支持音量，留作合成后处理预留
    "min_chars": 1,       # 少于这个字数不朗读
    "max_chars": 3000,    # 超过截断
    "copy_key": "insert", # insert=Ctrl+Insert（安全）, ctrl_c=Ctrl+C
    "drag_only": True,    # True=只响应拖拽/双击选中；False=单击也检测
    "float_bar": True,    # 显示悬浮控制条
    "float_pos": None,    # [x, y]，None 表示自动
    "autostart": False,
    # 翻译：选中英文时在悬浮条里显示中文。
    # 请求完全由下面几项描述，换服务只改配置不动代码。
    "translate": {
        "enabled": False,
        "url": "",                                        # 例: http://your-server/translate
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "payload": {"from": "en", "to": "zh", "text": "{text}"},
        "result_path": "result",                          # 从返回 JSON 里取译文的字段路径
        "timeout": 5,
        "min_chars": 2,
        "max_chars": 1200,
        "skip_if_cjk_ratio": 0.15,                        # 中文占比超过它就当成中文内容，不翻
    },
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _writable(d: Path) -> bool:
    try:
        d.mkdir(parents=True, exist_ok=True)
        probe = d / ".write_test"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def data_dir() -> Path:
    """优先用 exe 同目录；只读目录（如 Program Files）则退到 %APPDATA%。"""
    d = app_dir()
    if _writable(d):
        return d
    alt = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    alt.mkdir(parents=True, exist_ok=True)
    return alt


CONFIG_PATH = data_dir() / "config.json"
LOG_PATH = data_dir() / "SelectSpeak.log"


class Config(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.load()

    def load(self):
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if k in DEFAULTS:
                        self[k] = v
        except Exception:
            pass

    def save(self):
        try:
            CONFIG_PATH.write_text(
                json.dumps(dict(self), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
