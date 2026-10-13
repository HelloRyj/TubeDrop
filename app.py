"""TubeDrop 启动入口；工作进程模式不加载 Qt。"""
from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path

if __name__ == '__main__' and len(sys.argv) > 1 and sys.argv[1] == '--worker':
    from worker import run
    sys.exit(run(sys.argv[2:]))

from PySide6.QtCore import QProcess, QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from core import duration_label, normalize_url, platform_name, thumbnail_url_allowed
from ui import build_window
from version import VERSION


class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__()
        self.setWindowTitle('TubeDrop · YouTube / TikTok / 抖音下载')
        self.resize(780, 820)
        self.setMinimumSize(680, 600)
        self.settings = settings if settings is not None else QSettings('TubeDrop', 'TubeDrop')
        self.video = None
        self.identified_url = ''
        self.process = None
        self.cancelled = False
        self.terminal_event = False
        self.buffer = b''
        self.group_ready = False
        self.request_generation = 0
        self.network = QNetworkAccessManager(self)
        self.thumbnail_reply = None
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.setInterval(700)
        self.auto_timer.timeout.connect(self.auto_identify)
        self.timeout_timer = QTimer(self)
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self.identify_timeout)
        build_window(self)
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        folder = self.settings.value('folder', downloads or str(Path.home()))
        self.folder_edit.setText(folder if Path(folder).is_dir() else str(Path.home()))
        self.url_edit.textChanged.connect(self.url_changed)
        self.url_edit.returnPressed.connect(self.identify)
        self.paste_btn.clicked.connect(self.paste)
        self.identify_btn.clicked.connect(self.identify)
        self.download_btn.clicked.connect(self.download)
        self.cancel_btn.clicked.connect(self.cancel)
        self.folder_btn.clicked.connect(self.choose_folder)
        self.open_btn.clicked.connect(self.open_folder)
        self.output_format.currentIndexChanged.connect(self.format_changed)

    def is_busy(self):
        return self.process is not None

    def set_busy(self, busy):
        for widget in (self.url_edit, self.paste_btn, self.identify_btn,
                       self.folder_btn, self.proxy_edit, self.output_format):
            widget.setEnabled(not busy)
        output_format = self.output_format.currentData()
        capable = self.video is not None and self.video.get(
            'has_audio' if output_format == 'mp3' else 'has_video', True)
        self.quality.setEnabled(not busy and capable and output_format == 'mp4')
        self.download_btn.setEnabled(not busy and capable)
        self.cancel_btn.setEnabled(busy)

    def format_changed(self):
        self.set_busy(self.is_busy())
        if self.video:
            if self.output_format.currentData() == 'mp3' and not self.video.get('has_audio', True):
                self.show_status('此视频没有可下载的音轨，请选择 MP4。', error=True)
            else:
                self.show_status('已选择保存格式，可以开始下载。')

    def show_status(self, text, error=False):
        self.status.setText(text)
        self.status.setAccessibleName(f'操作状态：{text}')
        self.status.setStyleSheet('color: #b3261e;' if error else 'color: #636366;')

    def url_changed(self):
        self.auto_timer.stop()
        self.video = None
        self.identified_url = ''
        self.request_generation += 1
        self.download_btn.setEnabled(False)
        self.quality.clear()
        self.quality.addItem('识别后选择', None)
        self.quality.setEnabled(False)
        self.thumbnail.clear()
        self.thumbnail.setText('▶')
        self.video_title.setText('等待识别')
        self.video_detail.setText('视频信息将在这里显示。')
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.show_status('准备就绪，先粘贴一个视频链接。')
        self.auto_timer.start()

    def auto_identify(self):
        if not self.is_busy():
            try:
                normalize_url(self.url_edit.text())
            except ValueError:
                return
            self.identify()

    def paste(self):
        self.url_edit.setText(QApplication.clipboard().text().strip())
        self.identify()

    def identify(self):
        if self.is_busy():
            return
        self.auto_timer.stop()
        try:
            url = normalize_url(self.url_edit.text())
        except ValueError as error:
            self.show_status(str(error), error=True)
            return
        self.video = None
        self.identified_url = url
        self.video_title.setText('正在识别视频…')
        self.video_detail.setText('正在获取标题和可用画质，请稍候。')
        self.start_worker('identify', url)
        self.timeout_timer.start(90000)
        self.show_status(f'正在连接 {platform_name(url)} 并识别视频…')

    def worker_command(self, action, url):
        if getattr(sys, 'frozen', False):
            if sys.platform == 'win32':
                return str(Path(sys.executable).with_name('TubeDropWorker.exe')), [action, url]
            return sys.executable, ['--worker', action, url]
        executable = Path(sys.executable)
        if sys.platform == 'win32' and executable.name.lower() == 'pythonw.exe':
            executable = executable.with_name('python.exe')
        return str(executable), [str(Path(__file__).resolve()), '--worker', action, url]

    def start_worker(self, action, url, extra=None):
        self.cancelled = False
        self.terminal_event = False
        self.group_ready = False
        self.buffer = b''
        process = QProcess(self)
        self.process = process
        process.readyReadStandardOutput.connect(self.read_events)
        # 始终读取 stderr，避免缓冲区满导致后台进程卡住。
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(self.worker_finished)
        process.errorOccurred.connect(self.process_error)
        program, args = self.worker_command(action, url)
        args += extra or []
        if proxy := self.proxy_edit.text().strip():
            args += ['--proxy', proxy]
        self.set_busy(True)
        self.progress.setRange(0, 0)
        process.start(program, args)

    def read_events(self):
        if not self.process:
            return
        self.buffer += bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line, self.buffer = self.buffer.split(b'\n', 1)
            try:
                event = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if not self.cancelled:
                self.handle_event(event)

    def handle_event(self, event):
        kind = event.get('type')
        if kind == 'started':
            self.group_ready = True
        elif kind == 'metadata':
            self.terminal_event = True
            self.video = event['video']
            self.identified_url = self.video.get('url') or self.identified_url
            self.video_title.setText(self.video['title'])
            details = [self.video.get('platform'), self.video['channel'], duration_label(self.video['duration'])]
            self.video_detail.setText('  ·  '.join(item for item in details if item))
            self.quality.clear()
            self.quality.addItem('最高可用画质', None)
            for height in self.video['heights']:
                self.quality.addItem(f'{height}p', height)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.show_status('识别完成。选择格式和保存位置，然后开始下载。')
            self.load_thumbnail(self.video.get('thumbnail'))
        elif kind == 'progress':
            percent = event.get('percent')
            if percent is None:
                self.progress.setRange(0, 0)
            else:
                self.progress.setRange(0, 100)
                self.progress.setValue(int(percent))
            if event.get('phase') == 'processing':
                self.show_status('正在生成 MP3 音频，请稍候…' if self.output_format.currentData() == 'mp3'
                                 else '正在准备下一段音视频或合并文件，请稍候…')
            else:
                pieces = ['正在下载']
                if percent is not None:
                    pieces.append(f'{percent:.0f}%（当前音视频流）')
                if speed := event.get('speed'):
                    pieces.append(f'{speed / 1024 / 1024:.1f} MB/s')
                if event.get('eta') is not None:
                    pieces.append(f"预计剩余 {int(event['eta'])} 秒")
                self.show_status('  ·  '.join(pieces))
        elif kind == 'complete':
            path = Path(event['path'])
            if path.is_file():
                self.terminal_event = True
                self.progress.setRange(0, 100)
                self.progress.setValue(100)
                self.show_status(f'下载完成：{path.name}')
            else:
                self.handle_event({'type': 'error', 'message': '下载文件不存在，请重试。'})
        elif kind == 'error':
            self.terminal_event = True
            self.progress.setRange(0, 100)
            self.show_status(event['message'], error=True)
            if self.video is None:
                self.video_title.setText('暂时无法识别')
                self.video_detail.setText('检查链接或网络后，可点击“识别视频”重试。')

    def load_thumbnail(self, url):
        if self.thumbnail_reply:
            self.thumbnail_reply.abort()
        address = QUrl(url or '')
        if not thumbnail_url_allowed(url or ''):
            return
        generation = self.request_generation
        request = QNetworkRequest(address)
        request.setTransferTimeout(10000)
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                             QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        reply = self.network.get(request)
        self.thumbnail_reply = reply

        def received():
            if generation == self.request_generation and reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap = QPixmap()
                if pixmap.loadFromData(bytes(reply.readAll())):
                    self.thumbnail.setPixmap(pixmap.scaled(
                        self.thumbnail.size(), Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation))
            if self.thumbnail_reply is reply:
                self.thumbnail_reply = None
            reply.deleteLater()
        reply.finished.connect(received)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, '选择视频保存目录', self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)
            self.settings.setValue('folder', folder)

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_edit.text()))

    def download(self):
        if not self.video or self.is_busy():
            return
        folder = Path(self.folder_edit.text())
        if not folder.is_dir():
            self.show_status('保存目录不存在，请重新选择。', error=True)
            return
        output_format = self.output_format.currentData()
        extra = ['--folder', str(folder), '--output-format', output_format]
        if output_format == 'mp4':
            if height := self.quality.currentData():
                extra += ['--height', str(height)]
        self.start_worker('download', self.identified_url, extra)
        self.show_status('正在准备下载并刷新视频地址…')

    def stop_process(self, hard=False):
        if not self.process:
            return
        pid = self.process.processId()
        if sys.platform == 'win32':
            # Console 后台程序不能依靠 WM_CLOSE；Job Object 清理子进程。
            self.process.kill()
            return
        if os.name == 'posix' and pid and self.group_ready:
            try:
                os.killpg(pid, signal.SIGKILL if hard else signal.SIGTERM)
                return
            except ProcessLookupError:
                pass
        self.process.kill() if hard else self.process.terminate()

    def cancel(self):
        if not self.process:
            return
        self.cancelled = True
        self.timeout_timer.stop()
        self.cancel_btn.setEnabled(False)
        self.show_status('正在取消…')
        process = self.process
        self.stop_process()
        # 不阻塞界面；仅当原进程仍运行时升级为强制结束。
        QTimer.singleShot(1500, lambda: self.stop_process(hard=True)
                          if self.process is process else None)

    def identify_timeout(self):
        if self.process:
            self.cancel()
            self.show_status('识别超时，请检查网络或代理设置后重试。', error=True)

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.terminal_event = True
            self.show_status('无法启动下载进程，请重新打开应用。', error=True)
            self.worker_finished(1)

    def worker_finished(self, exit_code=0, *_):
        self.timeout_timer.stop()
        self.read_events()
        process = self.process
        self.process = None
        if process:
            process.deleteLater()
        self.set_busy(False)
        self.progress.setRange(0, 100)
        if self.cancelled:
            self.progress.setValue(0)
            if '超时' not in self.status.text():
                self.show_status('已取消。未完成的临时文件可能保留在保存目录，可重新开始。')
            if self.video is None:
                self.video_title.setText('识别已取消')
                self.video_detail.setText('可重新粘贴链接，或点击“识别视频”。')
        elif not self.terminal_event:
            self.show_status('下载进程意外结束，请重新尝试。', error=True)

    def closeEvent(self, event):
        self.auto_timer.stop()
        if self.thumbnail_reply:
            self.thumbnail_reply.abort()
        if self.process:
            process = self.process
            self.cancel()
            if not process.waitForFinished(1500):
                self.stop_process(hard=True)
                process.waitForFinished(1000)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('TubeDrop')
    app.setApplicationVersion(VERSION)
    app.setStyle('Fusion')
    app.setFont(QFont('PingFang SC' if sys.platform == 'darwin' else 'Segoe UI', 11))
    window = Window()
    icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'icon.png'
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
