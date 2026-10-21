import json
import os
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app import Window


def contrast_ratio(first, second):
    def luminance(color):
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize('dark', [False, True])
@pytest.mark.parametrize('control', ['output_format', 'quality'])
def test_dropdown_text_stays_readable_across_system_palettes(qt_app, tmp_path, dark, control):
    from PySide6.QtGui import QColor, QPalette
    original = qt_app.palette()
    palette = QPalette(original)
    palette.setColor(QPalette.ColorRole.Base, QColor('#202124' if dark else '#ffffff'))
    palette.setColor(QPalette.ColorRole.Text, QColor('#ffffff' if dark else '#202124'))
    qt_app.setPalette(palette)
    widget = Window(QSettings(str(tmp_path / 'theme.ini'), QSettings.Format.IniFormat))
    try:
        combo = getattr(widget, control)
        combo.setEnabled(True)
        widget.show()
        combo.showPopup()
        qt_app.processEvents()
        view = combo.view()
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            colors = view.palette()
            for text, background in ((QPalette.ColorRole.Text, QPalette.ColorRole.Base),
                                     (QPalette.ColorRole.HighlightedText, QPalette.ColorRole.Highlight)):
                assert contrast_ratio(colors.color(group, text), colors.color(group, background)) >= 4.5
        combo.hidePopup()
    finally:
        widget.close()
        qt_app.setPalette(original)
        qt_app.processEvents()


def wait_until(predicate, timeout=5000):
    end = time.monotonic() + timeout / 1000
    while time.monotonic() < end:
        if predicate():
            return
        QTest.qWait(20)
    assert predicate(), '状态转换超时'


@pytest.mark.parametrize('input_method', ['keyboard', 'mouse'])
def test_styled_dropdown_keeps_format_selection_working(window, qt_app, input_method):
    from PySide6.QtCore import Qt
    window.handle_event({'type': 'metadata', 'video': {
        'title': '测试作品', 'channel': '作者', 'duration': 10, 'thumbnail': None,
        'heights': [1080, 720], 'has_audio': True, 'has_video': True,
    }})
    window.show()
    combo = window.output_format
    combo.showPopup()
    qt_app.processEvents()
    view = combo.view()
    if input_method == 'keyboard':
        QTest.keyClick(view, Qt.Key.Key_End)
        QTest.keyClick(view, Qt.Key.Key_Return)
    else:
        index = combo.model().index(combo.findData('flac'), 0)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=view.visualRect(index).center())
    assert combo.currentData() == 'flac'
    assert not view.isVisible()
    assert not window.quality.isEnabled()
    assert window.download_btn.isEnabled()


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


def test_tiktok_metadata_uses_resolved_link_for_download(window):
    url = 'https://www.tiktok.com/@creator/video/6748451240264420610'
    window.handle_event({'type': 'metadata', 'video': {
        'title': 'TikTok 视频', 'channel': '作者', 'duration': 13,
        'heights': [720], 'thumbnail': None, 'platform': 'TikTok', 'url': url,
    }})
    window.set_busy(False)
    assert window.identified_url == url
    assert 'TikTok' in window.video_detail.text()
    assert window.download_btn.isEnabled()


def test_mp3_selection_disables_quality_and_passes_format(window):
    window.handle_event({'type': 'metadata', 'video': {
        'title': '抖音视频', 'channel': '作者', 'duration': 13,
        'heights': [720], 'thumbnail': None, 'platform': '抖音',
        'url': 'https://www.douyin.com/video/6961737553342991651',
        'has_audio': True, 'has_video': True,
    }})
    window.output_format.setCurrentIndex(1)
    assert not window.quality.isEnabled()
    calls = []
    window.start_worker = lambda *args: calls.append(args)
    window.download()
    extra = calls[0][2]
    assert extra[extra.index('--output-format') + 1] == 'mp3'
    assert '--height' not in extra
    window.set_busy(True)
    assert not window.output_format.isEnabled()
    window.set_busy(False)
    window.output_format.setCurrentIndex(0)
    assert window.quality.isEnabled()


def test_silent_video_cannot_be_downloaded_as_mp3(window):
    window.handle_event({'type': 'metadata', 'video': {
        'title': '无音轨视频', 'channel': '作者', 'duration': 13,
        'heights': [720], 'thumbnail': None, 'has_audio': False, 'has_video': True,
    }})
    window.set_busy(False)
    assert window.download_btn.isEnabled()
    window.output_format.setCurrentIndex(1)
    assert not window.download_btn.isEnabled()
    assert '音轨' in window.status.text()


def test_window_has_no_access_validation_controls(window):
    from PySide6.QtWidgets import QPushButton, QLabel
    texts = [widget.text() for widget in window.findChildren(QPushButton) + window.findChildren(QLabel)]
    assert not any('Cookie' in text or '访问验证' in text for text in texts)
    assert not hasattr(window, 'cookies_path')
    window.set_busy(True)
    assert not window.output_format.isEnabled()
    window.set_busy(False)
    assert window.output_format.isEnabled()


def test_gallery_switches_formats_and_completed_directory_is_recognized(window, tmp_path):
    window.handle_event({'type': 'metadata', 'video': {
        'title': '咖啡', 'channel': '作者', 'duration': None, 'heights': [],
        'media_type': 'images', 'image_count': 3, 'has_video': False, 'has_audio': False,
    }})
    window.set_busy(False)
    assert window.output_format.currentData() == 'original'
    assert {window.output_format.itemData(i) for i in range(window.output_format.count())} == {
        'original', 'jpg', 'png', 'webp'}
    assert '3 张图片' in window.video_detail.text()
    assert window.download_btn.isEnabled() and not window.quality.isEnabled()
    folder = tmp_path / 'gallery'; folder.mkdir()
    paths = []
    for i in range(3):
        file = folder / f'{i}.png'; file.write_bytes(b'image'); paths.append(str(file))
    window.handle_event({'type': 'complete', 'path': str(folder), 'paths': paths,
                         'media_type': 'images', 'image_count': 3})
    assert '3 张图片' in window.status.text() and window.progress.value() == 100
    (folder / '1.png').unlink()
    window.handle_event({'type': 'complete', 'path': str(folder), 'paths': paths,
                         'media_type': 'images', 'image_count': 3})
    assert '不完整' in window.status.text()


def test_flac_ui_explains_lossy_source_and_disables_video_quality(window):
    window.handle_event({'type': 'metadata', 'video': {
        'title': 'Test', 'channel': '作者', 'duration': 10, 'heights': [720],
        'has_audio': True, 'has_video': True, 'audio_quality': 'lossy',
    }})
    window.output_format.setCurrentIndex(window.output_format.findData('flac'))
    window.set_busy(False)
    assert not window.quality.isEnabled() and window.download_btn.isEnabled()
    assert '有损' in window.format_hint.text()
    assert '不会提升' in window.format_hint.text()
    window.url_changed()
    assert not window.download_btn.isEnabled()


def test_gallery_music_formats_are_available_only_with_audio(window):
    window.handle_event({'type': 'metadata', 'video': {
        'title': 'Test', 'channel': '作者', 'duration': None, 'heights': [],
        'media_type': 'images', 'image_count': 2, 'has_video': False, 'has_audio': True,
    }})
    window.output_format.setCurrentIndex(window.output_format.findData('flac'))
    assert '配乐' in window.format_hint.text()
