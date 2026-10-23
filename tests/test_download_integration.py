"""真实 HTTP 与 FFmpeg；仅替换外部平台的元数据请求。"""
import functools
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import imageio_ffmpeg
import yt_dlp
import pytest

from worker import run


@pytest.mark.parametrize(('url', 'video_id', 'extractor'), [
    ('https://youtu.be/BaW_jenozKc', 'BaW_jenozKc', 'Youtube'),
    ('https://www.tiktok.com/@creator/video/6748451240264420610', '6748451240264420610', 'TikTok'),
    ('https://www.douyin.com/video/6961737553342991651', '6961737553342991651', 'Douyin'),
])
@pytest.mark.parametrize(('output_format', 'source_codec', 'source_ext'), [
    ('mp4', 'aac', 'm4a'), ('mp3', 'aac', 'm4a'),
    ('flac', 'aac', 'm4a'), ('flac', 'libopus', 'opus'),
])
def test_real_download_merge_and_final_file(tmp_path, monkeypatch, capsys, url, video_id, extractor,
                                          output_format, source_codec, source_ext):
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
                    '-c:a', source_codec, str(media / f'audio.{source_ext}')], check=True)
    # 短视频平台的音频选项可能是单独的背景音乐，MP3 应优先提取视频原音轨。
    subprocess.run([ffmpeg, '-v', 'error', '-i', str(media / 'video.mp4'),
                    '-i', str(media / f'audio.{source_ext}'), '-c', 'copy',
                    str(media / 'combined.mp4')], check=True)
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=880:sample_rate=44100', '-t', '1.5',
                    '-c:a', 'aac', str(media / 'music.m4a')], check=True)

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(media)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    info = {
        'id': video_id, 'title': '../../本地合并测试', 'duration': 0.5,
        'extractor': extractor.lower(), 'extractor_key': extractor,
        'webpage_url': url,
        'formats': [
            {'format_id': 'audio', 'url': origin + (f'/audio.{source_ext}' if extractor == 'Youtube' else '/music.m4a'),
             'ext': source_ext if extractor == 'Youtube' else 'm4a',
             'vcodec': 'none', 'acodec': 'opus' if source_codec == 'libopus' and extractor == 'Youtube' else 'mp4a.40.2', 'abr': 128},
            {'format_id': 'video', 'url': origin + '/video.mp4', 'ext': 'mp4',
             'vcodec': 'avc1', 'acodec': 'none', 'height': 90, 'width': 160},
            {'format_id': 'combined', 'url': origin + '/combined.mp4', 'ext': 'mp4',
             'vcodec': 'avc1', 'acodec': 'opus' if source_codec == 'libopus' else 'aac', 'height': 90, 'width': 160},
        ],
    }
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', lambda *_args, **_kwargs: info)
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        # 测试进程不加入 job，实际后台子进程由专门的 Windows 取消测试覆盖。
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    try:
        code = run(['download', url, '--folder', str(destination), '--output-format', output_format])
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
    assert final.suffix == '.' + output_format
    assert final.stat().st_size > 1000
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(final)],
                           capture_output=True, text=True)
    assert 'Audio:' in probe.stderr
    if output_format == 'mp4':
        assert 'Video:' in probe.stderr
    else:
        assert 'Video:' not in probe.stderr
        assert 'Audio: ' + output_format in probe.stderr
        import re
        seconds = float(re.search(r'Duration: 00:00:([0-9.]+)', probe.stderr)[1])
        assert seconds < 1, 'MP3 应保存原视频声音，不能下载更长的独立背景音乐'
    assert subprocess.run([ffmpeg, '-v', 'error', '-i', str(final), '-f', 'null', '-'],
                          capture_output=True).returncode == 0
    if output_format == 'flac':
        # STREAMINFO 的有效位深；s32 只是 FFmpeg 的内存格式，不能据此判断文件位深。
        with final.open('rb') as stream:
            header = stream.read(42)
        assert header[:4] == b'fLaC'
        bits = ((int.from_bytes(header[18:26], 'big') >> 36) & 31) + 1
        assert bits <= 24, '有损音源不应生成兼容性较差的 32 位 FLAC'
        if sys.platform == 'darwin':
            decoded = subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16',
                                      str(final), str(tmp_path / 'apple-decoded.wav')], capture_output=True)
            assert decoded.returncode == 0, decoded.stderr.decode(errors='replace')


@pytest.mark.parametrize('bits', [24, 32])
def test_flac_preserves_lossless_pcm_samples(tmp_path, monkeypatch, capsys, bits):
    from pathlib import Path
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source = tmp_path / 'original.wav'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'aevalsrc=0.234567*sin(2*PI*440*t):s=48000:d=0.2',
                    '-c:a', f'pcm_s{bits}le', str(source)], check=True)
    destination = tmp_path / 'saved'; destination.mkdir()
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    info = {'id': 'BaW_jenozKc', 'title': 'Lossless', 'extractor': 'youtube', 'extractor_key': 'Youtube',
            'formats': [{'format_id': 'pcm', 'url': f'http://127.0.0.1:{server.server_port}/original.wav',
                         'ext': 'wav', 'acodec': f'pcm_s{bits}le', 'vcodec': 'none'}]}
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', lambda *a, **k: info)
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    try:
        assert run(['download', 'https://youtu.be/BaW_jenozKc', '--folder', str(destination), '--output-format', 'flac']) == 0
    finally:
        server.shutdown(); server.server_close(); thread.join()
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]['source_lossless']
    output = Path(events[-1]['path'])
    def pcm(path):
        return subprocess.run([ffmpeg, '-v', 'error', '-i', str(path), '-c:a', 'pcm_s32le',
                               '-f', 's32le', '-'], check=True, capture_output=True).stdout
    original = pcm(source)
    assert original == pcm(output)
    assert any(original[i + 1] for i in range(0, len(original), 4)), '样例确实包含超过 16 位的有效音频数据'


@pytest.mark.parametrize('fmt', ['mp3', 'flac'])
def test_gallery_music_uses_audio_formats(tmp_path, monkeypatch, capsys, fmt):
    import worker
    from pathlib import Path
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    source = tmp_path / 'music.flac'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'sine=d=0.2', str(source)], check=True)
    destination = tmp_path / 'saved'; destination.mkdir()
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_): pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    info = {'id': '7696358352017148859', 'title': '配乐', 'extractor': 'douyin', 'extractor_key': 'Douyin',
            'media_type': 'images', 'images': [{'urls': ['https://p3.douyinpic.com/photo.jpg']}],
            'formats': [{'format_id': 'music', 'url': f'http://127.0.0.1:{server.server_port}/music.flac',
                         'ext': 'flac', 'acodec': 'flac', 'vcodec': 'none'}]}
    monkeypatch.setattr(worker, 'extract_share_video', lambda *a, **k: info)
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    try:
        code = run(['download', 'https://www.douyin.com/note/7696358352017148859',
                    '--folder', str(destination), '--output-format', fmt])
    finally:
        server.shutdown(); server.server_close(); thread.join()
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert code == 0, events
    final = Path(events[-1]['path'])
    assert final.suffix == '.' + fmt
    if fmt == 'flac':
        assert final.read_bytes() == source.read_bytes(), 'FLAC 原文件应直接保留，不二次编码'
