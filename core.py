"""与界面无关的链接、画质和依赖处理。"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw or len(raw) > 4096 or any(ord(c) < 32 for c in raw):
        raise ValueError('请粘贴有效的 YouTube 视频链接。')
    if '://' not in raw:
        raw = 'https://' + raw
    try:
        parts = urlsplit(raw)
        if (parts.scheme not in {'http', 'https'} or parts.username or parts.password
                or parts.port not in {None, 80, 443}):
            raise ValueError
        host = parts.hostname
        path = parts.path.rstrip('/')
        if host == 'youtu.be':
            video_id = path[1:]
        elif host in HOSTS:
            if path == '/watch':
                values = parse_qs(parts.query).get('v', [])
                video_id = values[0] if len(values) == 1 else ''
            elif path.startswith(('/shorts/', '/embed/', '/live/')):
                video_id = path.split('/', 2)[2]
            else:
                video_id = ''
        else:
            video_id = ''
        if not VIDEO_ID.fullmatch(video_id):
            raise ValueError
    except ValueError:
        raise ValueError('请使用 YouTube 单个视频链接（支持普通视频和 Shorts）。') from None
    # 仅传递视频 ID，去除播放列表、跳转参数和分享追踪信息。
    return f'https://www.youtube.com/watch?v={video_id}'


def available_heights(formats: list[dict]) -> list[int]:
    return sorted({int(f['height']) for f in formats
                   if f.get('height') and f.get('vcodec') not in {None, 'none'}}, reverse=True)


def format_selector(height: int | None) -> str:
    if height is None:
        return 'bv*+ba/b'
    if not isinstance(height, int) or not 1 <= height <= 16384:
        raise ValueError('画质参数无效。')
    # 每个回退分支都保留上限，防止静默下载更高分辨率。
    return f'bv*[height<={height}]+ba/b[height<={height}]'


def runtime_path(name: str) -> str | None:
    if getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS) / 'bin' / name
        if bundled.is_file():
            return str(bundled)
    found = shutil.which(name)
    if found:
        return found
    # Finder 启动的应用 PATH 通常不包含 Homebrew。
    for root in (Path('/opt/homebrew/bin'), Path('/usr/local/bin'), Path.home() / '.local/bin'):
        if (root / name).is_file():
            return str(root / name)
    return None


def dependency_options() -> dict:
    import imageio_ffmpeg
    options = {'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe()}
    if node := runtime_path('node'):
        options['js_runtimes'] = {'node': {'path': node}}
    elif deno := runtime_path('deno'):
        options['js_runtimes'] = {'deno': {'path': deno}}
    else:
        raise RuntimeError('未找到 JavaScript 运行环境，请安装 Node.js 22+ 或 Deno 2.3+。')
    return options


def human_error(message: str) -> str:
    clean = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
    lower = clean.lower()
    if any(word in lower for word in ('sign in', 'private video', 'age-restricted', 'members-only')):
        return '此视频要求登录或访问权限，当前版本无法下载。可尝试其他公开视频。'
    if any(word in lower for word in ('timed out', 'timeout', 'network', 'proxy', 'connection', 'resolve')):
        return '网络连接失败，请检查是否能访问 YouTube，或配置代理后重试。'
    if '403' in lower or '429' in lower or 'bot' in lower:
        return 'YouTube 暂时限制了访问，请稍后重试或更换可访问 YouTube 的网络。'
    if any(word in lower for word in ('unavailable', 'removed', 'not available')):
        return '视频不可用、已删除或受到地区限制，请尝试其他链接。'
    if 'requested format' in lower:
        return '所选画质暂不可用，请重新识别或选择其他画质。'
    if any(word in lower for word in ('permission denied', 'no space left', 'read-only')):
        return '保存失败，请检查目录写入权限和剩余磁盘空间。'
    return clean.removeprefix('ERROR: ').strip()[:600] or '操作失败，请重试。'


def duration_label(seconds: int | None) -> str:
    if not seconds:
        return '时长未知'
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    return f'{hours}:{minutes:02}:{seconds:02}' if hours else f'{minutes}:{seconds:02}'
