# SelectSpeak · 划词朗读

> 在 Windows 上选中任意文字，松手就自动读出来。

![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)
[![release](https://img.shields.io/github/v/release/JKtian-14/SelectSpeak?color=0078D4&label=download)](https://github.com/JKtian-14/SelectSpeak/releases/latest)

英文一句话：**Select any text in any Windows app — it gets read aloud automatically.** Powered by Microsoft Edge neural TTS.

---

## 下载

**[⬇ 下载 SelectSpeak.exe](https://github.com/JKtian-14/SelectSpeak/releases/latest)** — 单文件约 21 MB，免安装，**不需要装 Python 或任何运行时**。

双击运行，托盘出现蓝色喇叭图标，没有主窗口。然后去任意程序里拖选一段文字，松手就开始读。

想自己编译或改代码 → 见下方「从源码运行」。

---

## 它解决什么问题

Windows 没有原生的划词朗读。系统自带的"讲述人"要接管整个屏幕；Edge 浏览器的"朗读"只管浏览器里；各种 TTS 软件要么要你复制粘贴、要么要你先开一个窗口。

SelectSpeak 只做一件事：**选中即读**。全局鼠标钩子监听拖选动作，抓出选中的文字，走微软 Edge 的神经语音念出来。没有主窗口，托盘常驻，不打断你正在做的事。

## 功能

- **选中即读** —— 拖选、双击选词、三击选段都会触发，不用按任何键
- **音质好** —— 微软 Edge 的在线神经语音，中文有晓晓 / 云希 / 云健 / 云扬，还有东北话、陕西话、粤语、台湾腔
- **响应快** —— 从选中到出声约 0.5 秒（见下方"技术实现"）
- **悬浮控制条** —— 暂停 / 继续 / 停止 / 语速 / 换音色，可拖动，读完自动消失
- **不污染剪贴板** —— 抓完把原剪贴板文本还原
- **终端安全** —— 用 `Ctrl+Insert` 而不是 `Ctrl+C` 抓词，不会误触发中断信号
- **长文本不卡顿** —— 自动分句 + 双缓冲，一句在播时下一句已经在合成

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
| 进度条 + `2/4` | 当前第几句 / 共几句 |

右键托盘图标：总开关、悬浮条显隐、语速、音色、停止、退出。

## 构建

需要 **Python 3.12**（官方安装包默认带 tkinter；微软商店版和部分精简版没有）。

```bash
pip install -r requirements.txt
python main.py        # 直接运行
python build.py       # 打包成 dist/SelectSpeak.exe（单文件，约 21 MB）
```

打包脚本会自动生成图标并调用 PyInstaller，产物是一个不依赖 Python 环境的 exe。

## 技术实现

有意思的地方有三处，都跟"延迟"和"不打扰"有关。

### 1. 复用 WebSocket，把延迟从 2s 压到 0.5s

`edge-tts` 库每次合成都新建一条 WebSocket 连接，握手固定吃掉约 2 秒，**跟文本长短无关**。对"选中即读"来说这是致命的——你选完文字要愣两秒才出声。

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

### 3. 判定"有没有选中"用剪贴板序列号

抓词的方式是模拟复制。难点在于：**怎么知道这次复制真的抓到了东西**（而不是点了个空白处）？

读剪贴板内容对比不可靠（选中的内容可能和剪贴板原内容一样）。用 `GetClipboardSequenceNumber()` —— 每次剪贴板被写入，系统就把这个序列号加一。发送复制快捷键前后对比序列号，变了就是真抓到了。

同时用 `Ctrl+Insert` 而不是 `Ctrl+C`：终端里 `Ctrl+C` 是中断信号，划个词就把命令打断了。

## 已知限制

| 限制 | 原因 |
|---|---|
| 管理员权限的窗口抓不到词 | Windows UIPI 会拦截普通进程发送的按键。需要以管理员身份运行 SelectSpeak |
| 必须联网 | 语音是微软在线服务合成 |
| 剪贴板里的图片/文件会被替换成文本 | 模拟复制的固有代价（文本会还原，其他格式不会） |
| 少数程序不响应 `Ctrl+Insert` | 可在 `config.json` 里把 `copy_key` 改成 `ctrl_c` |

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

## 项目结构

```
main.py         入口，组装各模块 + 主循环
config.py       配置读写，只读目录自动回退
tts_engine.py   Edge TTS 常驻连接引擎 + 分句
speech.py       朗读流水线：分句合成 + 双缓冲播放
player.py       MCI mp3 播放器
selection.py    全局鼠标钩子 + 抓取选中文字
ui_bar.py       悬浮控制条（tkinter Canvas 自绘）
ui_tray.py      托盘图标与菜单
build.py        一键打包
```

## License

[MIT](LICENSE)

语音合成使用微软 Edge 的在线朗读接口。本项目仅做客户端封装，不存储任何音频。
# SelectSpeak · 划词朗读

> 在 Windows 上选中任意文字，松手就自动读出来。

![platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4?logo=windows)
![python](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)

英文一句话：**Select any text in any Windows app — it gets read aloud automatically.** Powered by Microsoft Edge neural TTS.

---

## 它解决什么问题

Windows 没有原生的划词朗读。系统自带的"讲述人"要接管整个屏幕；Edge 浏览器的"朗读"只管浏览器里；各种 TTS 软件要么要你复制粘贴、要么要你先开一个窗口。

SelectSpeak 只做一件事：**选中即读**。全局鼠标钩子监听拖选动作，抓出选中的文字，走微软 Edge 的神经语音念出来。没有主窗口，托盘常驻，不打断你正在做的事。

## 功能

- **选中即读** —— 拖选、双击选词、三击选段都会触发，不用按任何键
- **音质好** —— 微软 Edge 的在线神经语音，中文有晓晓 / 云希 / 云健 / 云扬，还有东北话、陕西话、粤语、台湾腔
- **响应快** —— 从选中到出声约 0.5 秒（见下方"技术实现"）
- **悬浮控制条** —— 暂停 / 继续 / 停止 / 语速 / 换音色，可拖动，读完自动消失
- **不污染剪贴板** —— 抓完把原剪贴板文本还原
- **终端安全** —— 用 `Ctrl+Insert` 而不是 `Ctrl+C` 抓词，不会误触发中断信号
- **长文本不卡顿** —— 自动分句 + 双缓冲，一句在播时下一句已经在合成

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
| 进度条 + `2/4` | 当前第几句 / 共几句 |

右键托盘图标：总开关、悬浮条显隐、语速、音色、停止、退出。

## 构建

需要 **Python 3.12**（官方安装包默认带 tkinter；微软商店版和部分精简版没有）。

```bash
pip install -r requirements.txt
python main.py        # 直接运行
python build.py       # 打包成 dist/SelectSpeak.exe（单文件，约 21 MB）
```

打包脚本会自动生成图标并调用 PyInstaller，产物是一个不依赖 Python 环境的 exe。

## 技术实现

有意思的地方有三处，都跟"延迟"和"不打扰"有关。

### 1. 复用 WebSocket，把延迟从 2s 压到 0.5s

`edge-tts` 库每次合成都新建一条 WebSocket 连接，握手固定吃掉约 2 秒，**跟文本长短无关**。对"选中即读"来说这是致命的——你选完文字要愣两秒才出声。

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

### 3. 判定"有没有选中"用剪贴板序列号

抓词的方式是模拟复制。难点在于：**怎么知道这次复制真的抓到了东西**（而不是点了个空白处）？

读剪贴板内容对比不可靠（选中的内容可能和剪贴板原内容一样）。用 `GetClipboardSequenceNumber()` —— 每次剪贴板被写入，系统就把这个序列号加一。发送复制快捷键前后对比序列号，变了就是真抓到了。

同时用 `Ctrl+Insert` 而不是 `Ctrl+C`：终端里 `Ctrl+C` 是中断信号，划个词就把命令打断了。

## 已知限制

| 限制 | 原因 |
|---|---|
| 管理员权限的窗口抓不到词 | Windows UIPI 会拦截普通进程发送的按键。需要以管理员身份运行 SelectSpeak |
| 必须联网 | 语音是微软在线服务合成 |
| 剪贴板里的图片/文件会被替换成文本 | 模拟复制的固有代价（文本会还原，其他格式不会） |
| 少数程序不响应 `Ctrl+Insert` | 可在 `config.json` 里把 `copy_key` 改成 `ctrl_c` |

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

## 项目结构

```
main.py         入口，组装各模块 + 主循环
config.py       配置读写，只读目录自动回退
tts_engine.py   Edge TTS 常驻连接引擎 + 分句
speech.py       朗读流水线：分句合成 + 双缓冲播放
player.py       MCI mp3 播放器
selection.py    全局鼠标钩子 + 抓取选中文字
ui_bar.py       悬浮控制条（tkinter Canvas 自绘）
ui_tray.py      托盘图标与菜单
build.py        一键打包
```

## License

[MIT](LICENSE)

语音合成使用微软 Edge 的在线朗读接口。本项目仅做客户端封装，不存储任何音频。
