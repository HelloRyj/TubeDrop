# TubeDrop 1.4.0

简约 iOS 风格的 YouTube / TikTok / 抖音 桌面下载工具。粘贴链接，自动识别视频，选择画质和目录后保存为 MP4 视频或 MP3 音频。视频下载不设置速度上限或人为等待。

## 安装和使用

**macOS：**双击 `TubeDrop-1.4.0-macOS-arm64.pkg`，按系统安装器提示安装到“应用程序”，然后打开 TubeDrop。此包针对 Apple Silicon Mac，要求 macOS 14 或更新版本；Intel Mac 需要在 Intel 环境重新构建。

**Windows：**双击 `TubeDrop-1.4.0-Windows-x64-Setup.exe`，按向导安装，完成后从开始菜单打开 TubeDrop。默认安装到当前用户的 `%LOCALAPPDATA%\Programs\TubeDrop`，无需预装 Python、Node 或 FFmpeg。卸载可通过系统“已安装的应用”或开始菜单中的卸载入口完成，用户下载的视频和设置会保留。目标系统为 Windows 10 / 11 x64。

**验证边界：**Mac 包已完成测试、签名校验和安装载荷检查。Windows 安装器已在 Mac 上跨平台编译，运行组件使用官方 Windows 发行包且逐文件校验；当前没有 Windows 电脑，尚未完成 Windows 上的实际启动、下载和卸载验证。Windows 包应先在目标电脑试用。安装包尚未进行 Apple 公证或商业代码签名，外部分发可能出现系统发布者提示。

使用流程：粘贴 YouTube / youtu.be / Shorts / TikTok / 抖音链接 → 自动识别 → 选择 MP4 / MP3、画质和保存位置 → 开始下载。下载完成后点击“打开保存目录”。取消后可能保留未完成的临时文件；重新下载不会覆盖已有视频。

无法连接视频平台时，可输入自己的 HTTP 或 SOCKS5 代理地址，例如 `http://127.0.0.1:7890`。代理不保存。需要访问权限或人机验证的视频可能无法下载；当前版本不支持直播、播放列表、TikTok / 抖音图集或个人主页批量下载，也不会读取浏览器登录信息。

## TikTok 链接

支持完整 `https://www.tiktok.com/@作者/video/视频ID` 链接，以及 `vm.tiktok.com`、`vt.tiktok.com` 和 `www.tiktok.com/t/` 分享短链接。短链接逐跳校验，跳转到其他网站、直播、主页或图集时会停止。识别后使用解析出的完整视频链接下载。

TikTok 可能拒绝部分地区或 IP。已实测一条公开 TikTok 视频的识别和完整 MP4 下载。部分视频仍可能返回 IP 或地区访问限制；可尝试其他公开视频，或配置可访问 TikTok 的代理后重试。

## 抖音链接与格式选择

支持 `www.douyin.com/video/视频ID`、带 `modal_id` 的桌面视频链接、`www.iesdouyin.com/share/video/视频ID/` 和 `v.douyin.com` 分享短链接。可以粘贴包含一条链接的分享文案；多个链接会拒绝。短链接逐跳检查，拒绝跳到其他平台、直播、图集或不带视频 ID 的主页。

三个平台都可选择 **MP4 视频** 或 **MP3 音频 · 192 kbps**。MP4 可选画质；MP3 通过 FFmpeg 转换，画质选择自动禁用。TikTok / 抖音优先提取原视频的声音，避免保存成单独的背景音乐。原视频无音轨时，MP3 会提示不可用；转换不会提高原音频的音质。

抖音原详情接口失败时，1.3.2 会自动改用移动分享页解析。临时游客会话仅保留在下载进程内存中，无需登录、手动验证或导入 Cookie，不读取浏览器信息，也不使用第三方解析服务。已实测公开抖音视频 MP4 / MP3 下载成功；平台仍可能返回空数据或拒绝请求，不能保证所有作品都可下载。

分享页未提供可靠的流分辨率时，仅显示“最高可用画质”，保存平台实际返回的播放流；不将请求的 1080p 当作实际画质，也不承诺 4K。无法解析时可点击识别重试。

## 原始播放源与水印

1.4.0 默认排除明确标记为带水印的格式，以及 TikTok / 抖音的下载专用流，再选择画质。抖音分享页的已知官方水印接口会转换到同作品的原始播放接口；已实测 1080 × 1920 MP4，抽帧未见平台水印。过滤后没有播放视频时停止，不改用已知带水印版本或独立背景音乐。

**目前不能保证所有平台、所有作品都无水印。** TikTok 的部分播放流没有水印标签，但实际画面仍带水印：测试样例更换 H.264 / HEVC 和请求方式后仍出现 TikTok 标识。程序尚不能自动识别像素中的所有水印，不把“播放流”或“下载成功”视作无水印验证。YouTube 样例抽帧未见平台水印；创作者写入画面的标识、字幕不会被擦除或裁切。

MP3 仅提取原视频声音，不存在画面水印。MP4 / MP3 均保持不限速、无手动访问验证。

## 技术和源码运行

Python + PySide6 / Qt Widgets；yt-dlp 解析和下载；Node / EJS 处理 YouTube 脚本；curl_cffi 提供 TikTok 请求兼容性；FFmpeg 合并视频并转换 MP3。Qt 通过 QProcess 启动后台进程，并用 UTF-8 JSON Lines 交换事件。macOS 使用进程组，Windows 使用 Job Object 清理下载子进程。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python app.py
python -m pytest tests -q
```

源码运行需要 Python 3.10+、Node.js 22+ 或 Deno 2.3+。Windows 源码环境可使用 `.venv\Scripts\activate`。

## 重建安装包

macOS 构建（对应架构的 Mac）：

```bash
python build.py
```

Windows 安装器可在 Mac、Linux 或 Windows 上编译。先安装 [NSIS / makensis](https://nsis.sourceforge.io/Download)（Mac 可用 `brew install makensis`），然后下载清单锁定的官方 Windows 组件：

```bash
python installer/fetch_windows.py --cache /absolute/path/to/work/windows-cache
python pack_windows.py \
  --cache /absolute/path/to/work/windows-cache \
  --manifest installer/windows-manifest.json \
  --runtimes installer/windows-runtime-manifest.json \
  --payload /absolute/path/to/work/windows-payload
```

Windows 包内置 Python 3.14.8、Node 24.21.0 和 Windows x64 的 PySide6、FFmpeg、yt-dlp 依赖。Qt 发行包附带所需 Visual C++ 运行库。通过 Python 官方嵌入式运行时启动，系统 Python 环境不受影响。`windows-requirements.txt`、两个 JSON 清单记录版本、下载源和校验值。

测试和交付记录见 `VERIFICATION.md`；上游许可见 `THIRD_PARTY.md`。请仅下载你有权保存的内容。
