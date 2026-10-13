"""与界面无关的链接、画质和依赖处理。"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')
HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}
TIKTOK_HOSTS = {'tiktok.com', 'www.tiktok.com', 'm.tiktok.com'}
TIKTOK_SHORT_HOSTS = {'vm.tiktok.com', 'vt.tiktok.com'}
TIKTOK_VIDEO = re.compile(r'/@(?P<user>[A-Za-z0-9_.-]*)/video/(?P<id>[0-9]{10,25})')
DOUYIN_HOSTS = {'douyin.com', 'www.douyin.com', 'iesdouyin.com', 'www.iesdouyin.com'}


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw or len(raw) > 4096 or any(ord(c) < 32 and c not in '\r\n\t' for c in raw):
        raise ValueError('请粘贴有效的 YouTube、TikTok 或抖音视频链接。')
    if any(c.isspace() for c in raw):
        # 抖音复制的分享文案常带标题；只接受其中唯一的一条链接。
        links = re.findall(r'https?://[^\s<>"“”]+', raw)
        if len(links) != 1:
            raise ValueError('请一次粘贴一个视频链接。')
        raw = links[0].rstrip('，。；、！）')
    if '://' not in raw:
        raw = 'https://' + raw
    try:
        parts = urlsplit(raw)
        if (parts.scheme not in {'http', 'https'} or parts.username or parts.password
                or parts.port not in {None, 80, 443}):
            raise ValueError
        host = parts.hostname
        path = parts.path.rstrip('/')
        if host == 'v.douyin.com' and re.fullmatch(r'/[A-Za-z0-9_-]{5,100}', path):
            return f'https://v.douyin.com{path}/'
        if host in DOUYIN_HOSTS:
            match = re.fullmatch(r'/(?:video|share/video)/([0-9]{10,25})', path)
            if match:
                video_id = match[1]
            elif path in {'', '/discover'} or re.fullmatch(r'/user/[A-Za-z0-9_-]+', path):
                values = parse_qs(parts.query).get('modal_id', [])
                video_id = values[0] if len(values) == 1 else ''
            else:
                video_id = ''
            if not re.fullmatch(r'[0-9]{10,25}', video_id):
                raise ValueError
            return f'https://www.douyin.com/video/{video_id}'
        if host in TIKTOK_SHORT_HOSTS and re.fullmatch(r'/[A-Za-z0-9_]{5,100}', path):
            return f'https://{host}{path}/'
        if host in TIKTOK_HOSTS:
            if re.fullmatch(r'/t/[A-Za-z0-9_]{5,100}', path):
                return f'https://www.tiktok.com{path}/'
            if match := TIKTOK_VIDEO.fullmatch(path):
                return f'https://www.tiktok.com/@{match["user"] or "_"}/video/{match["id"]}'
            if match := re.fullmatch(r'/(?:share/video|embed)/([0-9]{10,25})', path):
                return f'https://www.tiktok.com/@_/video/{match[1]}'
            raise ValueError
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
        raise ValueError('请使用 YouTube、TikTok 或抖音单个视频链接，支持分享短链接。') from None
    # 仅传递视频 ID，去除播放列表、跳转参数和分享追踪信息。
    return f'https://www.youtube.com/watch?v={video_id}'


def platform_name(url: str) -> str:
    host = urlsplit(url).hostname
    if host in DOUYIN_HOSTS | {'v.douyin.com'}:
        return '抖音'
    return 'TikTok' if host in TIKTOK_HOSTS | TIKTOK_SHORT_HOSTS else 'YouTube'


def is_tiktok_short_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname in TIKTOK_SHORT_HOSTS or (
        parts.hostname in TIKTOK_HOSTS and parts.path.startswith('/t/'))


def is_share_short_url(url: str) -> bool:
    return is_tiktok_short_url(url) or urlsplit(url).hostname == 'v.douyin.com'


def thumbnail_url_allowed(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password:
        return False
    host = parts.hostname or ''
    return host in {'i.ytimg.com', 'img.youtube.com'} or any(
        host == domain or host.endswith('.' + domain)
        for domain in ('tiktokcdn.com', 'tiktokcdn-us.com', 'ibytedtos.com', 'byteoversea.com',
                       'douyinpic.com', 'douyincdn.com', 'byteimg.com'))


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
    executable = name + '.exe' if sys.platform == 'win32' else name
    if getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS) / 'bin' / executable
        if bundled.is_file():
            return str(bundled)
    if sys.platform == 'win32':
        # 官方嵌入式 Python 安装包将应用代码与运行组件分别放置。
        bundled = Path(__file__).resolve().parent.parent / 'bin' / executable
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


def human_error(message: str, platform: str = 'YouTube') -> str:
    clean = re.sub(r'\x1b\[[0-9;]*m', '', str(message))
    lower = clean.lower()
    if 'fresh cookies' in lower:
        return '抖音要求新的访问验证。请选择自己导出的 Cookie 文件，然后重新识别。'
    if any(word in lower for word in ('sign in', 'private video', 'age-restricted', 'members-only')):
        return '此视频要求登录或访问权限，当前版本无法下载。可尝试其他公开视频。'
    if any(word in lower for word in ('timed out', 'timeout', 'network', 'proxy', 'connection', 'resolve')):
        return f'网络连接失败，请检查是否能访问 {platform}，或配置代理后重试。'
    if any(word in lower for word in ('403', '429', 'bot', 'ip address is blocked')):
        return f'{platform} 暂时限制了访问，请稍后重试或更换网络。'
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
