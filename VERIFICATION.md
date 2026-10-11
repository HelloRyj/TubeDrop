# 交付验证

日期：2026-10-11。环境：Apple Silicon、macOS 26.1、Python 3.12.14、Node 22.22.3。

- 完整自动测试：`python -m pytest tests -q`，31 项通过。
- 链接：普通视频、分享短链接、Shorts、移动版与嵌入链接均规范化为官方 HTTPS 单视频地址；伪造域名、凭据、异常端口、播放列表、无效视频 ID 被拒绝。
- 画质：去除音频及分镜条目，去重排序；分辨率上限适用于所有下载回退分支。
- 工作进程：结构化错误、进程组组长启动回归测试通过。
- 真实本地集成：仅替换 YouTube 元数据响应，使用真实 HTTP 下载器和 FFmpeg，将独立视频和音频合并为含两个流的 MP4；输出路径在指定目录，标题中的路径字符被安全处理。
- Qt 界面：非法链接、切换链接后失效、错误恢复、取消时终止工作进程与其子进程、最终文件存在性、控件布局测试通过。
- 真实 YouTube：`jNQXAC9IVRw` 已成功识别标题、频道、19 秒时长、240p / 144p 画质；已通过源码及最终应用包下载并合并为 MP4。测试视频仅保存于本任务 work 目录。
- 可见窗口：已启动 TubeDrop.app，并通过原生界面读取验证。用户在窗口粘贴的另一个分享链接也已成功识别标题、时长和封面，下载按钮可用。
- 构建：PyInstaller 成功构建 macOS arm64 .app；捆绑 Python、Qt、yt-dlp、EJS、FFmpeg、Node。保留框架符号链接，应用约 260 MB。
- 签名：`codesign --verify --deep --strict TubeDrop.app` 通过。本地临时签名，未进行 Apple 公证。
- 依赖：完整锁定环境的 pip-audit 检查未发现已知漏洞。Qt 下载包与官方 PyPI SHA256 核对一致：`0867b709a724db28b161227c7d6ecb5ed10cc09226a53542417ac6dee1308239`。
- 语法：app.py、core.py、worker.py、ui.py、build.py 的 compileall 检查通过。

边界：真实网络验证不能保证所有视频与网络都可下载。YouTube 登录、人机验证、地区权限限制仍会影响可用性，应用会报告错误供用户重试。未测试 Windows、Intel Mac 或 macOS 14 的实际运行。
