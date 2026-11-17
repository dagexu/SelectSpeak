"""翻译模块：把选中的外文译成中文。

设计要点：
- 请求完全由 config.json 描述（url / method / headers / payload / result_path），
  换一个翻译服务只改配置，不动代码。
- 纯标准库 urllib，不引入 requests，exe 体积不变。
- 必须在后台线程跑，绝不能让网络请求挡住朗读。
"""
import json
import re
import threading
import urllib.parse
import urllib.request

# CJK 统一表意文字 + 扩展 A + 兼容表意文字
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

DEFAULTS = {
    "enabled": False,
    "url": "",
    "method": "POST",
    "headers": {"Content-Type": "application/json"},
    "payload": {"q": "{text}", "source": "en", "target": "zh", "format": "text"},
    "result_path": "translatedText",
    "timeout": 5,
    "min_chars": 2,
    "max_chars": 1200,
    "skip_if_cjk_ratio": 0.15,
}


def _subst(node, text):
    """把 payload 模板里所有 {text} 占位符替换成实际文本。"""
    if isinstance(node, str):
        return node.replace("{text}", text)
    if isinstance(node, list):
        return [_subst(v, text) for v in node]
    if isinstance(node, dict):
        return {k: _subst(v, text) for k, v in node.items()}
    return node


def _dig(obj, path):
    """按 "data.translation" 这种点号路径取值。"""
    cur = obj
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
                continue
            except Exception:
                return None
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
        if cur is None:
            return None
    return cur


class Translator:
    """异步翻译。同一时刻只关心最新一次请求，旧结果直接丢弃。"""

    def __init__(self, config, logger=None):
        self.cfg = config
        self._log = logger or (lambda *a: None)
        self._seq = 0
        self._lock = threading.Lock()
        # 强制直连：国内自建服务不该走系统代理，否则容易被代理拦成 502
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---------- 配置 ----------

    @property
    def conf(self) -> dict:
        raw = self.cfg.get("translate")
        merged = dict(DEFAULTS)
        if isinstance(raw, dict):
            merged.update({k: v for k, v in raw.items() if v is not None})
        return merged

    def available(self) -> bool:
        c = self.conf
        return bool(c.get("enabled")) and bool((c.get("url") or "").strip())

    # ---------- 判定要不要翻 ----------

    def should_translate(self, text: str) -> bool:
        if not self.available():
            return False
        text = (text or "").strip()
        c = self.conf
        chars = [ch for ch in text if not ch.isspace()]
        if len(chars) < int(c.get("min_chars") or 1):
            return False
        cjk = len(_CJK.findall(text))
        # 中文占比够高就当成中文内容，不翻
        if cjk and cjk / len(chars) >= float(c.get("skip_if_cjk_ratio") or 0.15):
            return False
        return True

    # ---------- 请求 ----------

    def _build(self, text: str):
        c = self.conf
        url = (c.get("url") or "").strip()
        method = (c.get("method") or "POST").upper()
        headers = {str(k): str(v) for k, v in (c.get("headers") or {}).items()}
        headers.setdefault("User-Agent", "SelectSpeak/1.1")
        payload = _subst(c.get("payload") or {"q": "{text}"}, text)

        if method == "GET":
            qs = urllib.parse.urlencode(payload, doseq=True)
            full = url + ("&" if "?" in url else "?") + qs
            return urllib.request.Request(full, headers=headers, method="GET")

        if isinstance(payload, dict) and headers.get("Content-Type", "").startswith(
            "application/json"
        ):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        else:
            body = urllib.parse.urlencode(payload).encode("utf-8")
            headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        return urllib.request.Request(url, data=body, headers=headers, method=method)

    def _parse(self, raw: bytes) -> str:
        c = self.conf
        text = raw.decode("utf-8", "replace").strip()
        try:
            data = json.loads(text)
        except Exception:
            # 接口直接返回纯文本
            return text[:2000]

        path = c.get("result_path") or ""
        if path:
            val = _dig(data, path)
            if isinstance(val, str):
                return val.strip()
        # 兜底：扫常见字段名
        for key in ("translatedText", "translation", "result", "text", "dst", "target"):
            val = _dig(data, key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        self._log(f"翻译响应里找不到译文，原始返回: {text[:200]}")
        return ""

    def translate(self, text: str) -> str:
        """同步翻译，供后台线程调用。失败返回空串，不抛异常。"""
        c = self.conf
        text = (text or "").strip()[: int(c.get("max_chars") or 1200)]
        if not text:
            return ""
        if not self.should_translate(text):
            return ""
        try:
            req = self._build(text)
            with self._opener.open(req, timeout=float(c.get("timeout") or 5)) as r:
                return self._parse(r.read())
        except Exception as e:
            self._log(f"翻译失败: {e}")
            return ""

    # ---------- 异步 ----------

    def translate_async(self, text: str, on_done, on_pending=None):
        """后台翻译，完成后在主线程回调 on_done(译文)。

        on_done 只会被最新一次请求触发，旧请求的结果直接丢弃。
        """
        with self._lock:
            self._seq += 1
            seq = self._seq

        if on_pending:
            on_pending()

        def work():
            result = self.translate(text)
            with self._lock:
                if seq != self._seq:
                    return  # 已经有新的划词了，丢弃
            try:
                on_done(result)
            except Exception as e:
                self._log(f"翻译回调异常: {e}")

        threading.Thread(target=work, daemon=True, name="translator").start()

    def cancel(self):
        """作废在途请求。"""
        with self._lock:
            self._seq += 1
