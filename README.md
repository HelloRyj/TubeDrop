# TubeDrop

一个中文桌面小工具：粘贴 YouTube 视频链接，自动识别后选择画质并下载。

## 使用

1. 双击旁边的 `TubeDrop.app`，打开独立窗口。
2. 点击“粘贴”或将视频链接粘贴到输入框。有效链接会自动开始识别。
3. 查看标题和画质，选择保存位置，然后点击“开始下载”。
4. 完成后点击“打开保存目录”，视频保存为 MP4。

支持普通视频、`youtu.be` 分享链接和 Shorts。选择分辨率时，工具下载不超过所选分辨率的可用视频；“最高可用画质”使用视频提供的最高画质。取消后可重新下载，未完成的 `.part` 等临时文件可能保留。应用不会覆盖已有视频。

默认保存到系统“下载”目录，修改后的目录会记住。若网络无法访问 YouTube，可在代理框输入自己的 HTTP 或 SOCKS5 代理地址，如 `http://127.0.0.1:7890`；不需要代理时留空。代理地址只用于当前会话，不保存。

识别失败时，界面会显示可操作的原因。当前版本不支持直播、播放列表、需要登录或权限验证的视频，也不会读取浏览器登录信息。封面请求失败不影响识别和下载。YouTube 对部分网络可能要求人机验证；遇到访问限制可稍后重试或换网络。

本次 .app 面向 Apple Silicon Mac，macOS 14 或更新版本。应用附带 Python、Qt、yt-dlp、FFmpeg 和 Node，不需要另行安装。它采用本地临时签名，没有 Apple 开发者公证，外部分发时可能需要在 Finder 中右键选择“打开”。

## 从源码运行

需要 Python 3.10+ 和 Node.js 22+ 或 Deno 2.3+。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

FFmpeg 二进制由 imageio-ffmpeg 包提供。YouTube 解析使用 `yt-dlp[default]` 附带的 EJS 脚本，执行引擎使用 Node 或 Deno。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python build.py
```

网络下载和合并由独立进程执行，以 JSON Lines 将状态传回 Qt 主进程。取消操作终止整个下载进程组，避免留下 FFmpeg 子进程。URL 先规范化为官方单视频链接；标题始终按纯文本展示；仅最终文件存在时才报告完成。

YouTube 的接口会变化，遇到平台更新可在源码环境更新 `yt-dlp[default]` 后重新打包。依赖锁定在 `requirements-lock.txt`；本次测试结果见 `VERIFICATION.md`。

## 上游项目

- [yt-dlp 使用和依赖](https://github.com/yt-dlp/yt-dlp)
- [YouTube JavaScript 运行环境说明](https://github.com/yt-dlp/yt-dlp/wiki/EJS)
- [Qt for Python](https://doc.qt.io/qtforpython-6/)
- [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)

请仅下载你有权保存的内容。
