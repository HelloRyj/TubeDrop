# TubeDrop 桌面下载工具

目标：在 macOS 与 Windows 独立窗口粘贴 YouTube 或 TikTok 链接，自动识别单个视频并下载到选定目录。界面采用简约 iOS 风格。

范围：普通 watch、youtu.be、Shorts、embed 链接，以及 TikTok 完整视频、vm/vt 和 /t/ 分享链接；标题、频道、时长、封面、可用画质；最高画质或指定分辨率；进度、取消、完成后打开目录。默认下载到系统下载目录，由用户在界面选择修改。播放列表、直播、登录、TikTok 图集和批量下载不在范围。

技术：macOS Python 3.12；Windows 官方 Python 3.14.8 嵌入式发行；PySide6 Essentials、yt-dlp[default,curl-cffi]、imageio-ffmpeg。Qt 主进程管理界面，独立工作进程执行网络请求与下载；UTF-8 JSON Lines 传递事件，取消终止工作进程及其子进程。macOS 提供 .app 和 .pkg；Windows 10/11 x64 提供 NSIS .exe 安装器，可在 Mac 上编译并附带官方 Windows 运行时。Windows 后台程序通过 python.exe 保留 stdout 通道，并使用 Job Object 保证取消时清理子进程。下载不配置速度上限或人为等待。

安装器：Mac 安装到 /Applications，更新同一应用；Windows 默认按当前用户安装，提供开始菜单、卸载入口，保留用户下载文件和设置。macOS 当前验证 Apple Silicon，Intel 需在相应架构构建。Windows 安装器可交付试用，但只有在 Windows 完成启动、下载、取消和卸载冒烟验证后才标记 Windows 运行验证通过。

命令：`python app.py` 启动；`python -m pytest tests -q` 测试；`python -m compileall -q .` 语法检查；`python build.py` 打包。

结构：app.py 界面和状态；core.py 链接、画质、依赖与错误处理；worker.py 下载进程；tests/ 逻辑、进程和界面测试；requirements.txt 运行依赖；build.py 打包。

代码：snake_case，简单中文注释，数据结构显式；不通过 shell 拼接执行用户输入。

验证：合法链接规范化；拒绝伪造主机、非视频链接、凭据和异常端口；画质不会静默下载更高分辨率；取消不会留下运行进程；仅最终文件存在时展示完成；识别和失败都可重新操作；使用真实网络检查解析和下载，若平台限制则明确报告测试边界。

边界：始终校验链接、限制单视频、保留现有文件、使用 HTTPS；下载只由用户点击触发；不收集账号、cookies 或浏览器数据；不删除用户文件；不自动发布。

TikTok 短链接最多解析五次跳转，每次请求前校验目标 URL；仅允许支持的 TikTok 主机和视频路径，拒绝跨平台跳转。封面仅允许 HTTPS 和已知平台 CDN，禁止自动重定向。已完成一条公开视频的真实 TikTok 识别和下载验证；其他视频的权限与平台访问限制可能影响可用性。
