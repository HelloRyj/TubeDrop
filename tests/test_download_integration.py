"""本地真实 HTTP 下载和 FFmpeg 合并；仅替换 YouTube 元数据请求。"""
import functools
import json
import os
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import imageio_ffmpeg
import yt_dlp

from worker import run


def test_real_download_merge_and_final_file(tmp_path, monkeypatch, capsys):
    media = tmp_path / 'media'
    media.mkdir()
    destination = tmp_path / 'saved'
    destination.mkdir()
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'color=c=green:s=160x90:r=10', '-t', '0.5', '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p', str(media / 'video.mp4')], check=True)
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=44100', '-t', '0.5',
                    '-c:a', 'aac', str(media / 'audio.m4a')], check=True)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(media)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    info = {
        'id': 'BaW_jenozKc', 'title': '../../本地合并测试', 'duration': 0.5,
        'extractor': 'youtube', 'extractor_key': 'Youtube',
        'webpage_url': 'https://www.youtube.com/watch?v=BaW_jenozKc',
        'formats': [
            {'format_id': 'audio', 'url': origin + '/audio.m4a', 'ext': 'm4a',
             'vcodec': 'none', 'acodec': 'mp4a.40.2', 'abr': 128},
            {'format_id': 'video', 'url': origin + '/video.mp4', 'ext': 'mp4',
             'vcodec': 'avc1', 'acodec': 'none', 'height': 90, 'width': 160},
        ],
    }
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', lambda *_args, **_kwargs: info)
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        # 测试进程不加入 job，实际后台子进程由专门的 Windows 取消测试覆盖。
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    try:
        code = run(['download', 'https://youtu.be/BaW_jenozKc', '--folder', str(destination)])
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 0, events
    assert events[-1]['type'] == 'complete'
    from pathlib import Path
    final = Path(events[-1]['path'])
    assert final.parent == destination
    assert final.suffix == '.mp4'
    assert final.stat().st_size > 1000
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(final)],
                           capture_output=True, text=True)
    assert 'Video:' in probe.stderr
    assert 'Audio:' in probe.stderr
