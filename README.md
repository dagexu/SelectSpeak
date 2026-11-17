# 开口读 · SelectSpeak

> 选中文字，松手就读。不按键，不开窗，不打断你正在做的事。

![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)
[![release](https://img.shields.io/github/v/release/dagexu/SelectSpeak?color=0078D4&label=download)](https://github.com/dagexu/SelectSpeak/releases/latest)

**English** — Select any text in any Windows app and it reads aloud immediately. No hotkey, no popup window, no clipboard pollution. Powered by Microsoft Edge neural TTS.

---

## 下载

**[⬇ 下载 开口读.exe（SelectSpeak.exe）](https://github.com/dagexu/SelectSpeak/releases/latest)** — 单文件约 21 MB，免安装，**不需要装 Python 或任何运行时**。

双击运行，托盘出现蓝色喇叭图标，没有主窗口。然后去任意程序里拖选一段文字，松手就开始读。

## 为什么做这个

我做跨境电商，每天要看大量英文——平台政策、供应商邮件、客户询盘、Reddit 上的用户抱怨。英语有一点基础，看得懂大概，但总有些词卡在那儿：**认识，却不确定怎么读。**

查一次要切窗口、复制、粘贴、开词典。一篇文章查二十次，注意力就碎成二十片，读不下去了。

所以做了开口读：划一下，读音当场出来，意思也当场出来，接着往下读。**不打断**，这是它唯一的设计目标。

对我自己它有两个用处：浏览国外网站时随手确认生词；做电商时边干活边把英语听进耳朵里。学语言最怕「专门抽时间学」，更好的方式是在你本来就要做的事情里，顺手把语言学掉。

## 它跟别的朗读工具差在哪

一句话：**别的工具是「先选中，再告诉它读」；开口读是「选中就是告诉它读」。**

| 工具 | 怎么触发 | 能读哪里 | 顺带翻译 | 价格 |
|---|---|---|---|---|
| **开口读** | **选中松手，零操作** | **任意 Windows 程序** | **悬浮条同步显示** | 免费开源 |
| [Read Aloud](https://github.com/Read-Aloud/read-aloud)（1.8k★） | 选中后点扩展图标 | 只有浏览器里 | 无 | 免费开源 |
| 朗读女 | 选中后按 F1 | 任意程序 | 无 | 免费闭源 |
| Voco.talk | 选中后点鼠标旁按钮，或 `Ctrl+Alt+R` | 任意程序 | 无 | 免费闭源 |
| Speechify / NaturalReader | 选中后点按钮，需登录 | 桌面 + 手机 | 有 | 约 ¥700–1000 / 年 |

差的那一下，恰好是这类工具最容易被放弃的地方：读一篇文章要按几十次快捷键，按到第三次就懒得用了。

> 顺带说清楚：Read Aloud 是浏览器扩展里做得最好那个，1.8k 星。它的限制不是做得不好，是**浏览器扩展管不到浏览器以外的窗口**。你要读 PDF、Word、终端输出、聊天记录，它一个都碰不到。

## 功能

- **选中即读** —— 拖选、双击选词、三击选段都会触发，不用按任何键
- **音质好** —— 微软 Edge 在线神经语音，中文有晓晓 / 云希 / 云健 / 云扬，还有东北话、陕西话、粤语、台湾腔
- **响应快** —— 从松手到出声约 0.5 秒（见下方「技术实现」）
- **悬浮控制条** —— 暂停 / 继续 / 停止 / 语速 / 换音色，可拖动；读完 **0.8 秒内淡出**，不留残影
- **英译中** —— 选中英文时，悬浮条里同步显示中文译文（需自备翻译接口，见下方「翻译」）
- **不污染剪贴板** —— 抓完把原剪贴板文本还原
- **终端安全** —— 用 `Ctrl+Insert` 而不是 `Ctrl+C` 抓词，不会误触发中断信号
- **长文本不卡顿** —— 自动分句 + 双缓冲，一句在播时下一句已经在合成

## 适合谁，不适合谁

**适合**：看英文文档、论文、新闻看到眼睛发酸；想边做别的事边听长文；受够了「打开朗读软件 → 粘贴 → 点播放」这套流程。

**不适合**：需要把语音存成 mp3 文件（用 [tts-vue](https://github.com/LokerL/tts-vue)）；要管理整本书书架（用电子书阅读器）；只在浏览器里用（装 Read Aloud 更省事）。

## 使用

从源码构建（见下），或直接跑 `python main.py`。

1. 启动后右下角托盘出现蓝色喇叭图标，**没有窗口**
2. 在任何程序里拖选一段文字
3. 屏幕下方弹出悬浮条

| 悬浮条元素 | 作用 |
|---|---|
| 蓝色圆按钮 | 暂停 / 继续 |
| 右侧圆按钮 | 停止 |
| `- 0% +` | 语速，每次 10%，范围 -50% ~ +100% |
| `云希` | 点开换音色 |
| 进度条 + `2 / 4` | 当前第几句 / 共几句 |
| 竖线 + 两行浅蓝文字 | 中文译文（选中英文且开启翻译时出现） |

右键托盘图标：总开关、悬浮条显隐、译文开关、语速、音色、停止、退出。

## 翻译

选中英文时在悬浮条里显示中文译文。译文和语音**并行请求**，谁先回来先显示，不会拖慢出声。

只对英文生效：中文内容不请求、不占版面。判定方式是数 CJK 字符占比，超过 `skip_if_cjk_ratio` 就当中文内容跳过。

默认关闭，接口和密钥都要自己填。任何接受 HTTP POST 的翻译服务都能接，请求格式写在 `config.json` 的 `translate` 段里：

```json
"translate": {
  "enabled": true,
  "url": "http://your-server/translate",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-token"
  },
  "payload": {"from": "en", "to": "zh", "text": "{text}"},
  "result_path": "result",
  "timeout": 5
}
```

- `{text}` 是占位符，会被替换成选中的原文
- `result_path` 是译文在返回 JSON 里的字段路径，支持 `data.translation` 这种点号嵌套
- 换服务只改这段配置，不用动代码

测试过的服务是 [MTranServer](https://github.com/xxnuo/MTranServer)（自建离线翻译，CPU 跑，单句几十毫秒）：

```
POST /translate
{"from": "en", "to": "zh", "text": "Hello"}
→ {"result": "你好"}
```

> 接口地址填 `http://` 而不是 `https://` 时注意：程序**强制直连、不走系统代理**。国内自建服务走代理容易被拦成 502。

## 构建

需要 **Python 3.12**（官方安装包默认带 tkinter；微软商店版和部分精简版没有）。

```bash
pip install -r requirements.txt
python main.py        # 直接运行
python build.py       # 打包成 dist/SelectSpeak.exe（单文件，约 21 MB）
```

打包脚本会自动生成图标并调用 PyInstaller，产物是一个不依赖 Python 环境的 exe。

## 技术实现

有意思的地方有三处，都跟「延迟」和「不打扰」有关。

### 1. 复用 WebSocket，把延迟从 2s 压到 0.5s

`edge-tts` 库每次合成都新建一条 WebSocket 连接，握手固定吃掉约 2 秒，**跟文本长短无关**。对「选中即读」来说这是致命的——你选完文字要愣两秒才出声。

实测发现微软这个接口允许**在同一条连接上连续做多轮合成**：

```
连接建立 1.2s（启动时付一次）
  ├─ turn 1  0.50s
  ├─ turn 2  0.55s
  ├─ turn 3  0.42s
  └─ turn 4  0.56s
```

所以 `tts_engine.py` 维护一条常驻连接：先发一次 `Path:speech.config`，之后每轮只发 `Path:ssml`，收到 `Path:turn.end` 表示该轮结束。连接空闲超过 180 秒才主动重连。

### 2. 播放用 winmm MCI，不用 pygame

`mciSendStringW` + `open "file.mp3" type mpegvideo alias x` 就能播 mp3，支持 `pause` / `resume` / `status position`，零额外依赖。MCI 没有播放结束回调，靠轮询 `status mode` 判断。

这也是 exe 只有 21 MB 的原因——没有音频库、没有 GUI 框架，界面是 tkinter 画的。

### 3. 判定「有没有选中」用剪贴板序列号

抓词的方式是模拟复制。难点在于：**怎么知道这次复制真的抓到了东西**（而不是点了个空白处）？

读剪贴板内容对比不可靠（选中的内容可能和剪贴板原内容一样）。用 `GetClipboardSequenceNumber()` —— 每次剪贴板被写入，系统就把这个序列号加一。发送复制快捷键前后对比序列号，变了就是真抓到了。

同时用 `Ctrl+Insert` 而不是 `Ctrl+C`：终端里 `Ctrl+C` 是中断信号，划个词就把命令打断了。

### 4. 译文不能挡住出声

翻译接口再快也是网络请求，不能让它排队在 TTS 前面。所以两个请求是**同时发**的：

```
on_text ─┬─> TTS 合成 ─> 播放
         └─> 翻译请求 ─> 悬浮条多出一行
```

实测本机自建 MTranServer（同一台服务器，内网转发）单句 30–70ms，比 TTS 的 500ms 还快，所以译文通常**先于声音**出现。悬浮条此时先显示「翻译中…」（高度 96 → 144），译文到了原地替换，不会跳。

两个细节：

- **请求带序号**。连续划词时，旧请求的返回直接丢弃（`Translator._seq`），否则慢请求会把新内容的译文覆盖掉。
- **强制直连**。`urllib` 在 Windows 上会读注册表代理，国内自建服务被代理一转就成了 502 超时。所以 `ProxyHandler({})` 显式禁用代理。

窗口高度切换还有个坑：译文往往在悬浮条**还没显示出来**的时候就返回了，而 Tk 对 `withdraw` 状态的窗口会忽略 `geometry()`，导致条出来后高度还是旧的。解法是在 `show()` 里按当前高度重新定一次尺寸。

## 已知限制

| 限制 | 原因 |
|---|---|
| 管理员权限的窗口抓不到词 | Windows UIPI 会拦截普通进程发送的按键。需要以管理员身份运行开口读 |
| 必须联网 | 语音是微软在线服务合成 |
| 剪贴板里的图片/文件会被替换成文本 | 模拟复制的固有代价（文本会还原，其他格式不会） |
| 少数程序不响应 `Ctrl+Insert` | 可在 `config.json` 里把 `copy_key` 改成 `ctrl_c` |
| 译文只有两行 | 悬浮条面积有限，长段落会截断。要完整译文学术阅读还是用浏览器插件 |

## 配置

首次运行在程序同目录生成 `config.json`（目录只读时会退到 `%APPDATA%\SelectSpeak\`），改完重启生效：

| 键 | 说明 | 默认 |
|---|---|---|
| `voice` | 音色 ID | `zh-CN-XiaoxiaoNeural` |
| `rate` | 语速偏移 -50 ~ 100 | `0` |
| `min_chars` | 少于多少字不读 | `1` |
| `max_chars` | 超过截断 | `3000` |
| `copy_key` | `insert` 或 `ctrl_c` | `insert` |
| `float_bar` | 显示悬浮条 | `true` |
| `enabled` | 总开关 | `true` |
| `translate` | 翻译配置（见上方「翻译」） | 关闭 |

## 项目结构

```
main.py         入口，组装各模块 + 主循环
config.py       配置读写，只读目录自动回退
tts_engine.py   Edge TTS 常驻连接引擎 + 分句
speech.py       朗读流水线：分句合成 + 双缓冲播放
player.py       MCI mp3 播放器
selection.py    全局鼠标钩子 + 抓取选中文字
translator.py   翻译请求（配置驱动，适配任意 HTTP 接口）
ui_bar.py       悬浮控制条（tkinter Canvas 自绘）
ui_tray.py      托盘图标与菜单
build.py        一键打包
```

## License

[MIT](LICENSE)

语音合成使用微软 Edge 的在线朗读接口。本项目仅做客户端封装，不存储任何音频。
