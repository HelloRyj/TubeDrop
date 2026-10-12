import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from app import Window


@pytest.fixture(scope='session')
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(qt_app, tmp_path):
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('folder', str(tmp_path))
    widget = Window(settings)
    yield widget
    widget.close()
    qt_app.processEvents()
