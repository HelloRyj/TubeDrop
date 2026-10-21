"""桌面窗口布局与样式；行为由 app.py 连接。"""
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListView, QProgressBar,
    QPushButton, QScrollArea, QLayout, QSizePolicy, QVBoxLayout, QWidget,
    QStyle, QStyledItemDelegate, QStyleOption,
)

STYLE = '''
QWidget { color: #1c1c1e; font-size: 14px; }
QWidget#root, QScrollArea { background: #f2f2f7; }
QFrame#card { background: #ffffff; border: 1px solid #e5e5ea; border-radius: 16px; }
QLabel#brand { font-size: 28px; font-weight: 650; }
QLabel#heading { font-size: 24px; font-weight: 650; }
QLabel#muted { color: #636366; font-size: 13px; }
QLabel#section { color: #636366; font-size: 12px; font-weight: 600; }
QLabel#title { font-size: 17px; font-weight: 600; }
QLabel#badge { color: #636366; font-size: 12px; }
QLabel#thumbnail { background: #f2f2f7; border-radius: 12px; color: #8e8e93; font-size: 28px; }
QLineEdit, QComboBox { background: #f2f2f7; border: 1px solid #f2f2f7; border-radius: 10px;
    min-height: 23px; padding: 10px 12px;
    selection-background-color: #0066cc; selection-color: #ffffff; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #0066cc; padding: 9px 11px; }
QComboBox { padding-right: 36px; border-color: #b8bdc9; }
QComboBox:hover:enabled { background: #e8effa; border-color: #8b9cb5; }
QComboBox:focus, QComboBox:on { border: 2px solid #0066cc; padding: 9px 35px 9px 11px; }
QLineEdit:disabled, QComboBox:disabled { color: #63636a; background: #eeeef3; border-color: #e5e5ea; }
QComboBox::drop-down { border: none; width: 32px; }
QComboBox::down-arrow { image: none; }
QScrollBar:vertical { background: #f2f2f7; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #b8bdc9; border-radius: 3px; min-height: 28px; }
QScrollBar::handle:vertical:hover { background: #8e8e93; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QPushButton { background: #f2f2f7; color: #0066cc; border: 1px solid #f2f2f7;
    border-radius: 10px; min-height: 23px; padding: 10px 16px; font-weight: 550; }
QPushButton:hover { background: #e8effa; border-color: #e8effa; }
QPushButton:focus { border: 2px solid #0066cc; padding: 9px 15px; }
QPushButton#primary { background: #0066cc; color: #ffffff; border: 1px solid #0066cc; }
QPushButton#primary:hover { background: #0056ad; }
QPushButton:disabled, QPushButton#primary:disabled { background: #e5e5ea; color: #76767c; border-color: #e5e5ea; }
QProgressBar { background: #e5e5ea; border: none; border-radius: 3px; height: 6px; }
QProgressBar::chunk { background: #0066cc; border-radius: 3px; }
'''


MENU_STYLE = '''
QFrame#selectionPopup { background: #ffffff; border: none; }
QListView { color: #1c1c1e; background: #ffffff;
    border: 1px solid #b8bdc9; border-radius: 10px; padding: 5px;
    selection-background-color: #0066cc; selection-color: #ffffff; outline: none; }
QListView::item { min-height: 24px; padding: 8px 12px;
    border-radius: 6px; color: #1c1c1e; background: #ffffff; }
QListView::item:hover { color: #1c1c1e; background: #e8effa; }
QListView::item:selected { color: #ffffff; background: #0066cc; }
QListView::item:disabled { color: #63636a; background: #f2f2f7; }
'''


def light_palette():
    """让浅色界面及弹出窗口使用一致配色，不混入系统深色主题。"""
    palette = QPalette()
    for role, color in {
        'Window': '#f2f2f7', 'WindowText': '#1c1c1e', 'Base': '#ffffff',
        'AlternateBase': '#f2f2f7', 'Text': '#1c1c1e', 'Button': '#f2f2f7',
        'ButtonText': '#1c1c1e', 'Highlight': '#0066cc', 'HighlightedText': '#ffffff',
        'PlaceholderText': '#636366', 'ToolTipBase': '#ffffff', 'ToolTipText': '#1c1c1e',
    }.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#63636a'))
    return palette


class SelectionBox(QComboBox):
    """统一菜单行距、配色和箭头，同时保留 Qt 的键盘及无障碍行为。"""
    def __init__(self):
        super().__init__()
        self.setPalette(light_palette())
        view = QListView(self)
        view.setPalette(light_palette())
        view.setMouseTracking(True)
        view.setUniformItemSizes(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setView(view)
        # 弹出容器是独立窗口，需要显式设置背景调色板。
        view.window().setObjectName('selectionPopup')
        view.window().setPalette(light_palette())
        view.window().setStyleSheet(MENU_STYLE)
        # 默认 ComboBox 菜单代理可能忽略 item 样式；使用标准列表代理。
        self.setItemDelegate(QStyledItemDelegate(view))

    def showPopup(self):
        # 弹窗首次打开前刷新行高，避免沿用样式加载前的紧凑尺寸。
        self.view().ensurePolished()
        self.view().doItemsLayout()
        super().showPopup()

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOption()
        option.initFrom(self)
        option.rect = QRect(self.width() - 28, (self.height() - 16) // 2, 16, 16)
        painter = QPainter(self)
        QApplication.style().drawPrimitive(QStyle.PrimitiveElement.PE_IndicatorArrowDown, option, painter, self)


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
    window.setPalette(light_palette())
    root = QWidget()
    root.setObjectName('root')
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(root)
    window.setCentralWidget(scroll)
    window.setStyleSheet(STYLE + MENU_STYLE)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(28, 20, 28, 20)
    layout.setSpacing(8)
    layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    header = QHBoxLayout()
    header.addWidget(label('TubeDrop', 'brand'))
    header.addStretch()
    header.addWidget(label('本地保存 · 不限速', 'badge'))
    layout.addLayout(header)
    layout.addWidget(label('粘贴链接，保存视频、图片或音频。', 'muted'))
    layout.addSpacing(8)

    link_card = card(layout)
    link_card.addWidget(label('作品链接', 'section'))
    link_row = QHBoxLayout()
    window.url_edit = QLineEdit()
    window.url_edit.setPlaceholderText('粘贴 YouTube、TikTok 或抖音链接')
    window.url_edit.setAccessibleName('YouTube、TikTok 或抖音作品链接')
    window.url_edit.setClearButtonEnabled(True)
    window.paste_btn = QPushButton('粘贴')
    window.identify_btn = QPushButton('识别作品')
    window.identify_btn.setObjectName('primary')
    link_row.addWidget(window.url_edit, 1)
    link_row.addWidget(window.paste_btn)
    link_row.addWidget(window.identify_btn)
    link_card.addLayout(link_row)
    link_card.addWidget(label('支持 YouTube、TikTok、抖音和分享短链接。', 'muted'))

    preview = card(layout)
    preview.addWidget(label('作品预览', 'section'))
    video_row = QHBoxLayout()
    video_row.setSpacing(20)
    window.thumbnail = label('▶', 'thumbnail')
    window.thumbnail.setFixedSize(160, 90)
    window.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.thumbnail.setAccessibleName('视频封面')
    video_row.addWidget(window.thumbnail)
    details = QVBoxLayout()
    window.video_title = label('等待识别', 'title', True)
    window.video_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    window.video_detail = label('作品信息将在这里显示。', 'muted', True)
    details.addStretch()
    details.addWidget(window.video_title)
    details.addWidget(window.video_detail)
    details.addStretch()
    video_row.addLayout(details, 1)
    preview.addLayout(video_row)

    save_card = card(layout)
    save_card.addWidget(label('下载设置', 'section'))
    format_row = QHBoxLayout()
    format_row.addWidget(label('保存格式', 'muted'))
    window.output_format = SelectionBox()
    window.output_format.addItem('MP4 视频', 'mp4')
    window.output_format.addItem('MP3 音频 · 192 kbps', 'mp3')
    window.output_format.addItem('FLAC 音频 · 无损编码', 'flac')
    window.output_format.setAccessibleName('下载输出格式')
    format_row.addWidget(window.output_format, 1)
    save_card.addLayout(format_row)
    settings_row = QHBoxLayout()
    settings_row.setSpacing(16)
    quality_column = QVBoxLayout()
    quality_column.addWidget(label('画质', 'muted'))
    window.quality = SelectionBox()
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
    window.folder_btn = QPushButton('更改')
    folder_row.addWidget(window.folder_edit, 1)
    folder_row.addWidget(window.folder_btn)
    folder_column.addLayout(folder_row)
    settings_row.addLayout(folder_column, 2)
    save_card.addLayout(settings_row)
    window.format_hint = label('优先无水印源；部分视频仍可能带水印。', 'muted', True)
    save_card.addWidget(window.format_hint)

    proxy_row = QHBoxLayout()
    proxy_row.addWidget(label('代理（可选）', 'muted'))
    window.proxy_edit = QLineEdit()
    window.proxy_edit.setPlaceholderText('http://127.0.0.1:7890；可留空')
    window.proxy_edit.setAccessibleName('网络代理地址')
    proxy_row.addWidget(window.proxy_edit, 1)
    save_card.addLayout(proxy_row)

    window.progress = QProgressBar()
    window.progress.setTextVisible(False)
    window.progress.setFixedHeight(6)
    window.progress.setValue(0)
    window.progress.setAccessibleName('下载进度')
    layout.addWidget(window.progress)
    window.status = label('准备就绪，粘贴链接即可开始。', 'muted', True)
    window.status.setAccessibleName('操作状态：准备就绪，粘贴链接即可开始。')
    window.status.setMinimumHeight(36)
    layout.addWidget(window.status)
    actions = QHBoxLayout()
    window.open_btn = QPushButton('打开保存目录')
    window.cancel_btn = QPushButton('取消')
    window.cancel_btn.setEnabled(False)
    window.download_btn = QPushButton('开始下载')
    window.download_btn.setObjectName('primary')
    window.download_btn.setMinimumWidth(180)
    window.download_btn.setEnabled(False)
    actions.addWidget(window.open_btn)
    actions.addStretch()
    actions.addWidget(window.cancel_btn)
    actions.addWidget(window.download_btn)
    layout.addLayout(actions)
    layout.addStretch()
    layout.addWidget(label('请仅下载你有权保存的内容。', 'muted'))
