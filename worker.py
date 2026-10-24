"""独立下载进程：stdout 只输出 JSON Lines，供 Qt 界面读取。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core import (available_heights, dependency_options, format_selector, human_error,
                  is_share_short_url, normalize_url, platform_name)
from douyin import extract_share_video
from images import IMAGE_FORMATS, download_gallery


def lossless_codec(codec: str | None) -> bool:
    return bool(codec and (codec in {'flac', 'alac'} or re.fullmatch(r'pcm_[su](?:8|16|24|32)(?:le|be)?', codec)))


def configure_stdio():
    # Windows 的管道默认编码可能是本地代码页；事件协议固定使用 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)


def emit(event_type: str, **data) -> None:
    print(json.dumps({'type': event_type, **data}, ensure_ascii=False), flush=True)


class QuietLogger:
    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        print(message, file=sys.stderr, flush=True)

    def error(self, message):
        print(message, file=sys.stderr, flush=True)


def resolve_video_url(url: str, proxy: str = '', fetch=None) -> str:
    url = normalize_url(url)
    if not is_share_short_url(url):
        return url
    platform = platform_name(url)
    if fetch is None:
        from curl_cffi import requests
        def fetch(address):
            response = requests.head(address, allow_redirects=False, impersonate='chrome',
                                     proxy=proxy or None, timeout=20)
            if response.status_code in {403, 405}:
                response.close()
                response = requests.get(address, allow_redirects=False, impersonate='chrome',
                                        proxy=proxy or None, timeout=20, stream=True)
            return response
    # 逐跳校验，禁止短链接带我们访问其他平台、用户主页或内网地址。
    for _ in range(5):
        response = fetch(url)
        try:
            response.raise_for_status()
            location = response.headers.get('Location')
            if response.status_code not in {301, 302, 303, 307, 308} or not location:
                raise ValueError(f'{platform} 短链接未能跳转到视频，请复制完整视频链接后重试。')
            try:
                destination = normalize_url(urljoin(url, location))
            except ValueError:
                raise ValueError(f'{platform} 短链接跳转目标无效，请复制完整视频链接后重试。') from None
            if platform_name(destination) != platform:
                raise ValueError(f'{platform} 短链接跳转到其他网站，已停止识别。')
        finally:
            response.close()
        if not is_share_short_url(destination):
            return destination
        url = destination
    raise ValueError(f'{platform} 短链接跳转次数过多，请使用完整视频链接。')


def video_summary(info: dict) -> dict:
    if not info or info.get('_type') in {'playlist', 'multi_video'}:
        raise ValueError('请使用单个视频链接。')
    if info.get('is_live') or info.get('live_status') in {'is_live', 'is_upcoming', 'post_live'}:
        raise ValueError('当前版本支持已发布的视频，暂不支持直播或预告。')
    formats = info.get('formats') or []
    extractor = str(info.get('extractor_key') or '').lower()
    audio_formats = [f for f in formats if f.get('acodec') not in {None, 'none'}]
    if extractor == 'douyin' and info.get('media_type') != 'images':
        audio_formats = [f for f in audio_formats if f.get('vcodec') not in {None, 'none'}]
    audio_quality = ('lossless' if any(lossless_codec(f.get('acodec')) for f in audio_formats)
                     else 'lossy' if audio_formats and all(str(f.get('acodec')).startswith(
                         ('aac', 'mp4a', 'mp3', 'opus', 'vorbis')) for f in audio_formats)
                     else 'unknown')
    return {
        'id': info.get('id'), 'title': info.get('title') or '未命名视频',
        'channel': info.get('uploader') or info.get('channel') or '未知频道',
        'duration': info.get('duration'), 'thumbnail': info.get('thumbnail'),
        'heights': available_heights(formats),
        'has_video': any(f.get('vcodec') not in {None, 'none'} for f in formats),
        'has_audio': bool(audio_formats),
        'media_type': info.get('media_type', 'video'),
        'image_count': len(info.get('images') or []),
        'audio_quality': audio_quality,
        'platform': '抖音' if extractor == 'douyin' else 'YouTube',
    }


class NoOriginalVideo(ValueError):
    """排除已知水印版本后，未找到候选播放源。"""


def original_video_formats(info: dict, platform: str) -> dict:
    # 元数据只能排除已知水印源，不能证明视频像素中没有水印。
    formats = []
    for source in info.get('formats') or []:
        candidate = dict(source)
        note = str(candidate.get('format_note') or '').lower()
        marked = (candidate.get('has_watermark') or candidate.get('watermarked')
                  or re.search(r'\bwatermarked\b', note)
                  or '/playwm/' in urlsplit(candidate.get('url') or '').path)
        # 抖音下载专用流可能带水印；只保留播放流与其音轨。
        download_copy = (platform == '抖音'
                         and str(candidate.get('format_id') or '').startswith('download'))
        if not marked and not download_copy:
            formats.append(candidate)
    if not formats or (platform == '抖音' and not any(
            f.get('vcodec') not in {None, 'none'} for f in formats)):
        raise NoOriginalVideo('未找到可用的原始播放源，已停止下载；不会自动改用已知带水印版本或背景音乐。')
    result = {**info, 'formats': formats}
    # 删除旧选择结果，保证后续画质选择只能使用过滤后的来源。
    for key in ('url', 'requested_downloads', 'requested_formats', 'format_id'):
        result.pop(key, None)
    return result


def extract_video_info(ydl, url: str, proxy: str = '') -> dict:
    from yt_dlp.utils import DownloadError
    platform = platform_name(url)
    if platform == '抖音' and '/note/' in url:
        return extract_share_video(url, proxy)
    try:
        raw = ydl.extract_info(url, download=False, process=False)
        info = original_video_formats(raw, platform)
    except (DownloadError, NoOriginalVideo):
        if platform != '抖音':
            raise
        # 旧详情接口失效时改用公开分享页，继续复用原有下载及格式转换。
        raw = extract_share_video(url, proxy)
        if raw.get('media_type') == 'images':
            return raw
        info = original_video_formats(raw, platform)
    return ydl.process_ie_result(info, download=False)


def base_options(proxy: str = '') -> dict:
    options = {
        'quiet': True, 'no_warnings': False, 'logger': QuietLogger(),
        'noplaylist': True, 'socket_timeout': 20, 'retries': 2,
        'extractor_retries': 2, 'cachedir': False,
        **dependency_options(),
    }
    if proxy:
        parts = urlsplit(proxy)
        if parts.scheme not in {'http', 'https', 'socks5', 'socks5h'} or not parts.hostname:
            raise ValueError('代理格式无效，例如 http://127.0.0.1:7890。')
        options['proxy'] = proxy
    return options


def download_options(folder: Path, height: int | None, output_format: str = 'mp4',
                     platform: str = 'YouTube') -> dict:
    if output_format not in {'mp4', 'mp3', 'flac'}:
        raise ValueError('请选择 MP4 视频、MP3 或 FLAC 音频格式。')
    token = uuid.uuid4().hex[:8]
    options = {
        'noplaylist': True,
        'outtmpl': str(folder / f'%(title).160B [%(id)s]-{token}.%(ext)s'),
        'overwrites': False, 'windowsfilenames': True,
    }
    if output_format in {'mp3', 'flac'}:
        # 短视频平台的独立音频可能只是配乐，优先提取完整视频的声音。
        selector = 'ba/b[acodec!=none]' if platform == 'YouTube' else 'b[acodec!=none][vcodec!=none]'
        if output_format == 'flac':
            bases = ['ba', 'b'] if platform == 'YouTube' else ['b[vcodec!=none]']
            lossless = [f'{base}[acodec{op}{codec}]' for op, codec in (
                ('=', 'flac'), ('=', 'alac'), ('^=', 'pcm_s'), ('^=', 'pcm_u'))
                for base in bases]
            selector = '/'.join([*lossless, selector])
        processor = {'key': 'FFmpegExtractAudio', 'preferredcodec': output_format}
        if output_format == 'mp3':
            processor['preferredquality'] = '192'
        options.update(format=selector, postprocessors=[processor])
    else:
        options.update(format=format_selector(height), merge_output_format='mp4',
                       postprocessors=[{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'}])
    return options


def run(argv: list[str]) -> int:
    configure_stdio()
    # 单独进程组让界面取消时同时终止 FFmpeg 和 JavaScript 子进程。
    try:
        if sys.platform == 'win32':
            from winjob import assign_worker_job
            assign_worker_job()
        elif os.name == 'posix' and os.getpgrp() != os.getpid():
            os.setsid()
    except OSError as error:
        emit('error', message=f'无法启动受控下载进程：{error}')
        return 1
    emit('started')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['identify', 'download'])
    parser.add_argument('url')
    parser.add_argument('--folder', default='')
    parser.add_argument('--height', type=int)
    parser.add_argument('--output-format', choices=['mp4', 'mp3', 'flac', *sorted(IMAGE_FORMATS)], default='mp4')
    parser.add_argument('--proxy', default='')
    args = parser.parse_args(argv)
    platform = '视频平台'
    try:
        url = normalize_url(args.url)
        platform = platform_name(url)
        import yt_dlp
        from yt_dlp.postprocessor import PostProcessor

        options = base_options(args.proxy)
        url = resolve_video_url(url, args.proxy)
        if args.action == 'identify':
            with yt_dlp.YoutubeDL(options) as ydl:
                info = extract_video_info(ydl, url, args.proxy)
            summary = video_summary(info)
            summary.update(platform=platform, url=url)
            if not summary['has_video'] and not summary['has_audio'] and not summary['image_count']:
                raise ValueError('未找到可下载的音视频，请稍后重试。')
            emit('metadata', video=summary)
            return 0

        folder = Path(args.folder).expanduser().resolve()
        if not args.folder or not folder.is_dir():
            raise ValueError('请选择存在的保存目录。')
        if args.output_format not in IMAGE_FORMATS:
            options.update(download_options(folder, args.height, args.output_format, platform))
        last_update = 0.0

        def progress(data):
            nonlocal last_update
            now = time.monotonic()
            if data['status'] == 'finished':
                emit('progress', phase='processing', percent=None)
            elif data['status'] == 'downloading' and now - last_update >= 0.2:
                total = data.get('total_bytes') or data.get('total_bytes_estimate')
                downloaded = data.get('downloaded_bytes') or 0
                emit('progress', phase='downloading',
                     percent=min(99, downloaded / total * 100) if total else None,
                     speed=data.get('speed'), eta=data.get('eta'),
                     downloaded=downloaded, total=total)
                last_update = now

        final_paths = []

        class FinalFile(PostProcessor):
            def run(self, info):
                final_paths.append(Path(info['filepath']).resolve())
                return [], info

        options['progress_hooks'] = [progress]
        # 再次解析以刷新临时下载地址；先拒绝直播，再允许写入。
        with yt_dlp.YoutubeDL(options) as ydl:
            info = extract_video_info(ydl, url, args.proxy)
            summary = video_summary(info)
            if args.output_format in IMAGE_FORMATS:
                if not summary['image_count']:
                    raise ValueError('此作品不是图集，请选择视频或音频格式。')
                result = download_gallery(info, folder, args.output_format, args.proxy, emit)
                emit('complete', **result)
                return 0
            if summary['image_count'] and args.output_format == 'mp4':
                raise ValueError('此作品是图集，请选择图片格式或可用的配乐格式。')
            if summary['image_count']:
                # 图集的音频明确是配乐，允许使用其独立音频流。
                ydl.params['format'] = download_options(folder, None, args.output_format, 'YouTube')['format']
                ydl.format_selector = ydl.build_format_selector(ydl.params['format'])
                info = ydl.process_ie_result(info, download=False)
            if args.output_format in {'mp3', 'flac'} and not summary['has_audio']:
                raise ValueError('此视频没有可下载的音轨，请选择 MP4 或尝试其他视频。')
            if args.output_format == 'mp4' and not summary['has_video']:
                raise ValueError('此链接仅有音频，请选择 MP3。')
            if args.output_format == 'flac' and re.fullmatch(r'pcm_[su]32(?:le|be)?', info.get('acodec') or ''):
                # 仅原始 PCM32 需要扩展位深；AAC/Opus 使用常规 FLAC，兼容更多播放器。
                ydl.params['postprocessor_args'] = {'extractaudio+ffmpeg_o': ['-strict', 'experimental']}
            ydl.add_post_processor(FinalFile(), when='after_move')
            ydl.process_ie_result(info, download=True)
        if not final_paths or not all(p.is_file() and p.stat().st_size > 0 and p.is_relative_to(folder)
                                      and p.suffix.lower() == '.' + args.output_format for p in final_paths):
            raise RuntimeError('下载未生成完整文件，请重试。')
        emit('complete', path=str(final_paths[-1]), output_format=args.output_format,
             source_lossless=lossless_codec(info.get('acodec')))
        return 0
    except Exception as error:
        emit('error', message=human_error(str(error), platform))
        return 1


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
