# 交付验证

## 1.1.0 — 2026-10-12

- 完整测试：35 项通过，包括 Windows 运行路径、pythonw/python 后台入口和中文 UTF-8 管道回归测试。Windows Job Object 的系统级行为尚需 Windows 实机确认。
- iOS 风格布局：780 × 760 离屏渲染、控件不裁剪检查通过，预览为 TubeDrop-iOS-preview.png。当前 Mac 锁屏，未执行新版可见窗口交互复核。
- macOS：生成 TubeDrop-1.1.0-macOS-arm64.pkg。安装载荷为 Applications/TubeDrop.app，禁止重定位，应用版本 1.1.0，升级策略为 upgrade。安装包完整展开成功，展开后的应用通过 codesign 深度严格校验。没有执行向系统 /Applications 的实际安装。
- 真实网络：新版 Mac 应用已识别测试视频 jNQXAC9IVRw，并实际下载含音视频的 MP4。测试文件仅写入本任务 work 目录。
- Windows：NSIS 3.13 在 Mac 上编译为 PE32 Unicode 安装器，内含 x64 Python 3.14.8、Node 24.21.0、Qt 和 FFmpeg；64 位 Windows 10/11 为目标系统。安装器为当前用户安装，提供开始菜单和卸载项，不删除用户下载与设置。
- Windows 组件：14 个 wheel 及 Python、Node ZIP 与官方 SHA256 一致；依赖元数据已按 Windows 3.14 环境验证。PySide6 包包含 Visual C++ 运行库。锁定依赖的 pip-audit 未发现已知漏洞。
- Windows 安装器归档：7-Zip 完整检查通过，4299 个文件；核实包含中文 UTF-8 工作进程、Job Object 模块、pythonw.exe、隔离路径配置、Node 和 Qt Widgets DLL。
- 语法检查、git diff --check 通过。下载没有配置 ratelimit 或人为等待。

Windows 上的实际安装、启动、识别、下载、取消及卸载尚未验证；当前没有 Windows 环境。此包作为试用安装器交付，不将跨平台编译成功等同于实机验证通过。安装包未做商业代码签名或 Apple 公证。

## 初始版本 — 2026-10-11

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
