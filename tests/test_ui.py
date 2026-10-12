import json
import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app import Window


def wait_until(predicate, timeout=5000):
    end = time.monotonic() + timeout / 1000
    while time.monotonic() < end:
        if predicate():
            return
        QTest.qWait(20)
    assert predicate(), '状态转换超时'


def test_invalid_link_is_actionable_without_starting_worker(window):
    window.url_edit.setText('https://evil.org')
    window.identify()
    assert not window.is_busy()
    assert '链接' in window.status.text()
    assert not window.download_btn.isEnabled()


def test_changing_url_invalidates_previous_video(window):
    window.url_edit.setText('https://youtu.be/BaW_jenozKc')
    window.auto_timer.stop()
    window.handle_event({'type': 'metadata', 'video': {
        'title': '<b>不可作为 HTML</b>', 'channel': '频道', 'duration': 65,
        'heights': [1080, 720], 'thumbnail': None,
    }})
    window.set_busy(False)
    assert window.download_btn.isEnabled()
    assert window.video_title.text() == '<b>不可作为 HTML</b>'
    window.url_edit.setText('https://youtu.be/YE7VzlLtp-4')
    window.auto_timer.stop()
    assert window.video is None
    assert not window.download_btn.isEnabled()


def test_error_event_restores_controls_after_worker_exit(window, tmp_path):
    script = tmp_path / 'failure.py'
    script.write_text('import json\nprint(json.dumps({"type":"error","message":"网络连接失败"}), flush=True)\n')
    window.worker_command = lambda action, url: (__import__('sys').executable, [str(script)])
    window.url_edit.setText('https://youtu.be/BaW_jenozKc')
    window.identify()
    wait_until(lambda: not window.is_busy())
    assert window.identify_btn.isEnabled()
    assert '网络连接失败' == window.status.text()
    assert not window.download_btn.isEnabled()


@pytest.mark.skipif(os.name != 'posix', reason='POSIX 进程组测试')
def test_cancel_stops_worker_and_child_process(window, tmp_path):
    script = tmp_path / 'sleep_worker.py'
    pid_file = tmp_path / 'child.pid'
    script.write_text(
        'import os, subprocess, sys, time, json\n'
        'os.setsid()\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"])\n'
        f'open({str(pid_file)!r}, "w").write(str(child.pid))\n'
        'print(json.dumps({"type":"started"}), flush=True)\n'
        'time.sleep(90)\n'
    )
    window.worker_command = lambda action, url: (__import__('sys').executable, [str(script)])
    window.url_edit.setText('https://youtu.be/BaW_jenozKc')
    window.identify()
    wait_until(lambda: window.group_ready)
    child_pid = int(pid_file.read_text())
    window.cancel()
    wait_until(lambda: not window.is_busy())
    assert '已取消' in window.status.text()
    assert window.identify_btn.isEnabled()

    def child_stopped():
        try:
            os.kill(child_pid, 0)
            return False
        except ProcessLookupError:
            return True
    wait_until(child_stopped)


def test_complete_requires_final_file(window, tmp_path):
    window.handle_event({'type': 'complete', 'path': str(tmp_path / 'missing.mp4')})
    assert '不存在' in window.status.text()
    path = tmp_path / 'video.mp4'
    path.write_bytes(b'video')
    window.handle_event({'type': 'complete', 'path': str(path)})
    assert '下载完成' in window.status.text()
    assert window.progress.value() == 100


def test_cards_do_not_clip_controls_at_default_window_size(window, qt_app):
    from PySide6.QtWidgets import QFrame
    window.show()
    qt_app.processEvents()
    cards = [frame for frame in window.findChildren(QFrame) if frame.objectName() == 'card']
    assert all(frame.height() >= frame.minimumSizeHint().height() for frame in cards)
