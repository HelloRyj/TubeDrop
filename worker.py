"""独立下载进程：stdout 只输出 JSON Lines，供 Qt 界面读取。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from core import available_heights, dependency_options, format_selector, human_error, normalize_url


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
    # 单独进程组让界面取消时同时终止 FFmpeg 和 JavaScript 子进程。
    if os.name == 'posix' and os.getpgrp() != os.getpid():
        os.setsid()
    emit('started')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['identify', 'download'])
    parser.add_argument('url')
    parser.add_argument('--folder', default='')
    parser.add_argument('--height', type=int)
    parser.add_argument('--proxy', default='')
    args = parser.parse_args(argv)
    try:
        url = normalize_url(args.url)
        import yt_dlp
        from yt_dlp.postprocessor import PostProcessor

        options = base_options(args.proxy)
        if args.action == 'identify':
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            summary = video_summary(info)
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
        emit('error', message=human_error(str(error)))
        return 1


if __name__ == '__main__':
    sys.exit(run(sys.argv[1:]))
