"""独立下载进程：stdout 只输出 JSON Lines，供 Qt 界面读取。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from core import (available_heights, dependency_options, format_selector, human_error,
                  is_tiktok_short_url, normalize_url, platform_name)


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
    if not is_tiktok_short_url(url):
        return url
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
                raise ValueError('TikTok 短链接未能跳转到视频，请复制完整视频链接后重试。')
            try:
                destination = normalize_url(urljoin(url, location))
            except ValueError:
                raise ValueError('TikTok 短链接跳转目标无效，请复制完整视频链接后重试。') from None
            if platform_name(destination) != 'TikTok':
                raise ValueError('TikTok 短链接跳转到其他网站，已停止识别。')
        finally:
            response.close()
        if not is_tiktok_short_url(destination):
            return destination
        url = destination
    raise ValueError('TikTok 短链接跳转次数过多，请使用完整视频链接。')


def video_summary(info: dict) -> dict:
    if not info or info.get('_type') in {'playlist', 'multi_video'}:
        raise ValueError('请使用单个视频链接。')
    if info.get('is_live') or info.get('live_status') in {'is_live', 'is_upcoming', 'post_live'}:
        raise ValueError('当前版本支持已发布的视频，暂不支持直播或预告。')
    return {
        'id': info.get('id'), 'title': info.get('title') or '未命名视频',
        'channel': info.get('uploader') or info.get('channel') or '未知频道',
        'duration': info.get('duration'), 'thumbnail': info.get('thumbnail'),
        'heights': available_heights(info.get('formats') or []),
        'platform': 'TikTok' if str(info.get('extractor_key') or '').lower().startswith('tiktok') else 'YouTube',
    }


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


def download_options(folder: Path, height: int | None) -> dict:
    token = uuid.uuid4().hex[:8]
    return {
        'noplaylist': True, 'format': format_selector(height),
        'outtmpl': str(folder / f'%(title).160B [%(id)s]-{token}.%(ext)s'),
        'overwrites': False, 'windowsfilenames': True,
        'merge_output_format': 'mp4',
        'postprocessors': [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'}],
    }


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
                info = ydl.extract_info(url, download=False)
            summary = video_summary(info)
            summary.update(platform=platform, url=url)
            if not summary['heights']:
                raise ValueError('未找到可下载的视频画质，请稍后重试。')
            emit('metadata', video=summary)
            return 0

        folder = Path(args.folder).expanduser().resolve()
        if not args.folder or not folder.is_dir():
            raise ValueError('请选择存在的保存目录。')
        options.update(download_options(folder, args.height))
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
            info = ydl.extract_info(url, download=False)
            video_summary(info)
            ydl.add_post_processor(FinalFile(), when='after_move')
            ydl.process_ie_result(info, download=True)
        if not final_paths or not all(p.is_file() and p.is_relative_to(folder) for p in final_paths):
            raise RuntimeError('下载未生成完整文件，请重试。')
        emit('complete', path=str(final_paths[-1]))
        return 0
    except Exception as error:
        emit('error', message=human_error(str(error), platform))
        return 1


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
