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
