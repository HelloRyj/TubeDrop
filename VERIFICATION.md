# 交付验证

## 1.2.0 — 2026-10-13

- 完整自动测试：67 项通过。新增 TikTok 链接规范化、短链接逐跳校验与次数上限、封面域名限制、识别后使用完整链接的界面回归测试；真实本地 HTTP / FFmpeg 下载集成覆盖 YouTube 和 TikTok 元数据。
- 真实 TikTok：公开视频 `@hankgreen1/video/7047596209028074758` 已通过源码和最终 Mac 应用下载为 MP4。最终应用产物 1,790,611 字节，21.27 秒，576 × 1024 HEVC 视频与 AAC 音频；FFmpeg 完整解码检查通过。
- YouTube 回归：最终 Mac 应用下载 `jNQXAC9IVRw` 成功，含 19.02 秒视频与音频，FFmpeg 完整解码检查通过。测试文件仅保存在本任务 work 目录。
- 短链接：自动测试验证合法逐跳解析、跨站/内网/主页拒绝和循环上限。实测的上游旧分享短链接跳转到 TikTok 首页，已正确报告需改用完整视频链接；未将该样例记为短链接下载成功。
- 访问限制：另一公开样例返回 TikTok IP 访问限制，程序正确显示平台错误；不能保证每个视频、地区或网络都可下载。
- macOS：生成 TubeDrop-1.2.0-macOS-arm64.pkg，完整展开成功。固定载荷 Applications/TubeDrop.app，禁止重定位，版本 1.2.0；展开后的应用通过 codesign 深度严格校验。未向系统 /Applications 执行实际安装。
- Windows：生成 TubeDrop-1.2.0-Windows-x64-Setup.exe；7-Zip 完整检查通过，共 4382 个文件。已核实包含新增 curl_cffi 原生 DLL、CFFI 后端和共享版本模块。17 个官方 wheel 的 SHA256 与清单一致。
- 依赖：Mac 环境与 Windows 锁定依赖分别通过 pip-audit，未发现已知漏洞；curl_cffi 已随两端安装包捆绑。
- 界面：更新 YouTube / TikTok 平台提示与输入说明，重新生成 iOS 风格离屏预览。当前 Mac 锁屏，未执行可见窗口交互复核。
- 语法检查、git diff --check 通过；下载仍未配置 ratelimit 或人为等待。安装器校验值见 TubeDrop-1.2.0-SHA256.txt。

Windows 上的实际安装、启动、识别、下载、取消及卸载尚未验证；当前没有 Windows 环境。安装包未做商业代码签名或 Apple 公证。实际短链接是否有效还取决于 TikTok 返回的跳转目标。

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
