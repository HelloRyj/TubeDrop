import json
import os
import subprocess
import sys
from pathlib import Path

import yt_dlp

from worker import run


def test_worker_identifies_douyin_without_user_access_files(monkeypatch, capsys):
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    monkeypatch.setattr('worker.base_options', lambda *_: {'quiet': True})
    def identify(ydl, url, **kwargs):
        assert ydl.params.get('cookiefile') is None
        assert ydl.params.get('cookiesfrombrowser') is None
        return {'id': '6961737553342991651', 'extractor_key': 'Douyin',
                'formats': [{'height': 720, 'vcodec': 'avc1', 'acodec': 'aac'}]}
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', identify)
    assert run(['identify', 'https://www.douyin.com/video/6961737553342991651']) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert events[-1]['type'] == 'metadata'
    assert events[-1]['video']['platform'] == '抖音'


def test_worker_no_longer_accepts_cookie_file_argument():
    script = Path(__file__).resolve().parents[1] / 'app.py'
    result = subprocess.run([sys.executable, str(script), '--worker', 'identify',
                             'https://www.douyin.com/video/6961737553342991651',
                             '--cookies', 'unused.txt'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 2
    assert 'unrecognized arguments' in result.stderr
