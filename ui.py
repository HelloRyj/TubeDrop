"""桌面窗口布局与样式；行为由 app.py 连接。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QLayout, QSizePolicy, QVBoxLayout, QWidget,
)

STYLE = '''
QWidget { color: #243831; font-family: "PingFang SC", "Helvetica Neue"; font-size: 14px; }
QWidget#root { background: #f4f5f1; }
QFrame#card { background: #ffffff; border: 1px solid #dce3dc; border-radius: 12px; }
QLabel#brand { font-size: 21px; font-weight: 650; }
QLabel#heading { font-size: 30px; font-weight: 650; }
QLabel#muted { color: #627067; font-size: 13px; }
QLabel#section { color: #627067; font-size: 12px; font-weight: 600; }
QLabel#title { font-size: 19px; font-weight: 600; }
QLabel#badge { color: #176646; background: #e6f1e8; border-radius: 6px; padding: 7px 12px; }
QLabel#thumbnail { background: #eaf0e9; border-radius: 8px; color: #65776b; font-size: 28px; }
QLineEdit, QComboBox { background: #fbfcfa; border: 1px solid #cbd6cd; border-radius: 7px;
    min-height: 23px; padding: 10px 12px; selection-background-color: #286c50; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #286c50; padding: 9px 11px; }
QLineEdit:disabled, QComboBox:disabled { color: #748179; background: #f1f3ef; }
QPushButton { background: #ffffff; border: 1px solid #cbd6cd; border-radius: 7px;
    min-height: 23px; padding: 10px 16px; font-weight: 550; }
QPushButton:hover { background: #edf3ed; border-color: #769d83; }
QPushButton:focus { border: 2px solid #286c50; padding: 9px 15px; }
QPushButton#primary { background: #226246; color: #ffffff; border: 1px solid #226246; }
QPushButton#primary:hover { background: #194c36; }
QPushButton:disabled, QPushButton#primary:disabled { background: #e9eee9; color: #77867b; border-color: #e0e6df; }
QProgressBar { background: #e9eee7; border: none; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #377c54; border-radius: 4px; }
'''


def label(text, name='', wrap=False):
    widget = QLabel(text)
    widget.setObjectName(name)
    # 视频标题等外部内容始终作为纯文本显示。
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    return widget


def card(parent_layout):
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 16, 20, 16)
    layout.setSpacing(8)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    parent_layout.addWidget(frame)
    return layout


def build_window(window):
    root = QWidget()
    root.setObjectName('root')
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(root)
    window.setCentralWidget(scroll)
    root.setStyleSheet(STYLE)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(28, 20, 28, 20)
    layout.setSpacing(8)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    header = QHBoxLayout()
    header.addWidget(label('↓  TubeDrop', 'brand'))
    header.addStretch()
    header.addWidget(label('桌面下载工具', 'badge'))
    layout.addLayout(header)
    layout.addWidget(label('粘贴链接，把视频带走。', 'heading'))
    layout.addWidget(label('识别视频 · 选择画质 · 保存到你的电脑', 'muted'))

    link_card = card(layout)
    link_card.addWidget(label('01   视频链接', 'section'))
    link_row = QHBoxLayout()
    window.url_edit = QLineEdit()
    window.url_edit.setPlaceholderText('https://www.youtube.com/watch?v=…')
    window.url_edit.setAccessibleName('YouTube 视频链接')
    window.url_edit.setClearButtonEnabled(True)
    window.paste_btn = QPushButton('粘贴')
    window.identify_btn = QPushButton('识别视频')
    window.identify_btn.setObjectName('primary')
    link_row.addWidget(window.url_edit, 1)
    link_row.addWidget(window.paste_btn)
    link_row.addWidget(window.identify_btn)
    link_card.addLayout(link_row)
    link_card.addWidget(label('支持普通视频、分享短链接和 Shorts；粘贴有效链接后自动识别。', 'muted'))

    preview = card(layout)
    preview.addWidget(label('02   视频预览', 'section'))
    video_row = QHBoxLayout()
    video_row.setSpacing(20)
    window.thumbnail = label('↓', 'thumbnail')
    window.thumbnail.setFixedSize(176, 99)
    window.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.thumbnail.setAccessibleName('视频封面')
    video_row.addWidget(window.thumbnail)
    details = QVBoxLayout()
    window.video_title = label('等待识别视频', 'title', True)
    window.video_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    window.video_detail = label('粘贴链接后，这里将显示标题、频道和时长。', 'muted', True)
    details.addStretch()
    details.addWidget(window.video_title)
    details.addWidget(window.video_detail)
    details.addStretch()
    video_row.addLayout(details, 1)
    preview.addLayout(video_row)

    save_card = card(layout)
    save_card.addWidget(label('03   下载设置', 'section'))
    settings_row = QHBoxLayout()
    settings_row.setSpacing(16)
    quality_column = QVBoxLayout()
    quality_column.addWidget(label('画质', 'muted'))
    window.quality = QComboBox()
    window.quality.addItem('识别后选择', None)
    window.quality.setEnabled(False)
    window.quality.setAccessibleName('下载画质')
    quality_column.addWidget(window.quality)
    settings_row.addLayout(quality_column, 1)
    folder_column = QVBoxLayout()
    folder_column.addWidget(label('保存位置', 'muted'))
    folder_row = QHBoxLayout()
    window.folder_edit = QLineEdit()
    window.folder_edit.setReadOnly(True)
    window.folder_edit.setAccessibleName('保存目录')
    window.folder_btn = QPushButton('选择…')
    folder_row.addWidget(window.folder_edit, 1)
    folder_row.addWidget(window.folder_btn)
    folder_column.addLayout(folder_row)
    settings_row.addLayout(folder_column, 2)
    save_card.addLayout(settings_row)

    proxy_row = QHBoxLayout()
    proxy_row.addWidget(label('代理（可选）', 'muted'))
    window.proxy_edit = QLineEdit()
    window.proxy_edit.setPlaceholderText('例如 http://127.0.0.1:7890；留空使用系统网络')
    window.proxy_edit.setAccessibleName('网络代理地址')
    proxy_row.addWidget(window.proxy_edit, 1)
    save_card.addLayout(proxy_row)

    window.progress = QProgressBar()
    window.progress.setTextVisible(False)
    window.progress.setFixedHeight(8)
    window.progress.setValue(0)
    window.progress.setAccessibleName('下载进度')
    layout.addWidget(window.progress)
    window.status = label('准备就绪，先粘贴一个视频链接。', 'muted', True)
    window.status.setAccessibleName('操作状态')
    window.status.setMinimumHeight(36)
    layout.addWidget(window.status)
    actions = QHBoxLayout()
    window.open_btn = QPushButton('打开保存目录')
    window.cancel_btn = QPushButton('取消')
    window.cancel_btn.setEnabled(False)
    window.download_btn = QPushButton('↓  开始下载')
    window.download_btn.setObjectName('primary')
    window.download_btn.setMinimumWidth(180)
    window.download_btn.setEnabled(False)
    actions.addWidget(window.open_btn)
    actions.addStretch()
    actions.addWidget(window.cancel_btn)
    actions.addWidget(window.download_btn)
    layout.addLayout(actions)
    layout.addStretch()
    layout.addWidget(label('视频保存在本机  ·  请仅下载你有权保存的内容', 'muted'))
