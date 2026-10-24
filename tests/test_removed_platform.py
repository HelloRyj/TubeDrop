import os

import pytest

from worker import resolve_video_url, run


@pytest.mark.parametrize('url', [
    'https://www.tiktok.com/@creator/video/6748451240264420610',
    'https://vm.tiktok.com/ZM123Abcd/',
    'https://vt.tiktok.com/ZSe4FqkKd/',
])
def test_removed_platform_is_rejected_before_resolving(url):
    calls = []
    def fetch(address):
        calls.append(address)
        raise RuntimeError('不应请求已移除的平台')
    with pytest.raises(ValueError, match='YouTube.*抖音'):
        resolve_video_url(url, fetch=fetch)
    assert not calls


@pytest.mark.parametrize('action', ['identify', 'download'])
def test_worker_rejects_removed_platform_before_network_setup(monkeypatch, action):
    events = []
    setups = []
    def options(*args):
        setups.append(args)
        raise RuntimeError('不应创建下载器')
    monkeypatch.setattr('worker.base_options', options)
    monkeypatch.setattr('worker.emit', lambda kind, **data: events.append({'type': kind, **data}))
    # 直接调用 worker 时，测试进程保持原有进程组。
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    assert run([action, 'https://www.tiktok.com/@creator/video/6748451240264420610']) == 1
    assert not setups
    assert events[-1]['type'] == 'error'
    assert 'YouTube' in events[-1]['message'] and '抖音' in events[-1]['message']


def test_ui_rejects_removed_platform_without_starting_worker(window, monkeypatch):
    starts = []
    monkeypatch.setattr(window, 'start_worker', lambda *args: starts.append(args))
    window.url_edit.setText('https://vm.tiktok.com/ZM123Abcd/')
    window.auto_timer.stop()
    window.auto_identify()
    window.identify()
    assert not starts
    assert not window.is_busy()
    assert not window.download_btn.isEnabled()
    assert 'YouTube' in window.status.text() and '抖音' in window.status.text()
