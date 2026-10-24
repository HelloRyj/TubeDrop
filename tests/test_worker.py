import json
import subprocess
import sys
from pathlib import Path

import pytest

from worker import video_summary, download_options


def test_summary_rejects_live_and_playlist():
    for info in ({'is_live': True}, {'_type': 'playlist'}, {'live_status': 'is_upcoming'}):
        with pytest.raises(ValueError):
            video_summary(info)


def test_summary_contains_only_display_metadata():
    result = video_summary({'id': 'BaW_jenozKc', 'title': '<b>Title</b>',
                            'duration': 65, 'uploader': 'Channel',
                            'formats': [{'height': 720, 'vcodec': 'avc1'}],
                            'url': 'https://temporary-signed.example'})
    assert result['title'] == '<b>Title</b>'
    assert result['heights'] == [720]
    assert 'url' not in result


def test_download_never_overwrites_existing_file(tmp_path):
    options = download_options(tmp_path, 720)
    assert options['overwrites'] is False
    assert str(tmp_path) in options['outtmpl']
    assert options['noplaylist'] is True
    assert options['format'].endswith('/b[height<=720]')


@pytest.mark.parametrize('platform', ['YouTube', '抖音'])
def test_mp3_options_extract_audio_without_video_remux(tmp_path, platform):
    options = download_options(tmp_path, 720, 'mp3', platform)
    assert 'height' not in options['format']
    assert 'merge_output_format' not in options
    assert options['postprocessors'] == [
        {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'},
    ]
    if platform != 'YouTube':
        assert options['format'].startswith('b[acodec!=none]')


def test_download_rejects_unknown_output_format(tmp_path):
    with pytest.raises(ValueError, match='格式'):
        download_options(tmp_path, None, 'wav')


def test_summary_reports_audio_capability_and_douyin_platform():
    result = video_summary({'extractor_key': 'Douyin', 'formats': [
        {'height': 720, 'vcodec': 'avc1', 'acodec': 'none'},
    ]})
    assert result['has_video'] is True
    assert result['has_audio'] is False
    assert result['platform'] == '抖音'


def test_worker_invalid_url_reports_structured_error():
    script = Path(__file__).resolve().parents[1] / 'app.py'
    result = subprocess.run([sys.executable, str(script), '--worker', 'identify',
                             'https://evil.org'], capture_output=True, text=True, timeout=15)
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 1
    assert events[-1]['type'] == 'error'
    assert '链接' in events[-1]['message']


def test_worker_runs_when_already_session_leader():
    script = Path(__file__).resolve().parents[1] / 'app.py'
    result = subprocess.run([sys.executable, str(script), '--worker', 'identify',
                             'https://evil.org'], capture_output=True, text=True,
                            timeout=15, start_new_session=True)
    assert result.returncode == 1
    events = [json.loads(line) for line in result.stdout.splitlines()]
    assert events[-1]['type'] == 'error'


def test_progress_pipe_handles_unicode_on_windows_locale(monkeypatch):
    import io
    import worker
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding='cp1252')
    monkeypatch.setattr(sys, 'stdout', stream)
    worker.configure_stdio()
    worker.emit('metadata', title='视频标题 · 日本語')
    stream.flush()
    assert json.loads(buffer.getvalue().decode('utf-8'))['title'] == '视频标题 · 日本語'
