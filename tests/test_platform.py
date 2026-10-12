import sys
from pathlib import Path

from core import runtime_path


def test_windows_bundled_runtime_uses_exe_suffix(monkeypatch, tmp_path):
    binary = tmp_path / 'bin' / 'node.exe'
    binary.parent.mkdir()
    binary.write_bytes(b'MZ')
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert runtime_path('node') == str(binary)


def test_windows_source_worker_uses_console_python(monkeypatch, window):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'executable', str(Path('C:/TubeDrop/runtime/pythonw.exe')))
    program, args = window.worker_command('identify', 'https://youtu.be/BaW_jenozKc')
    assert Path(program).name == 'python.exe'
    assert '--worker' in args


def test_windows_frozen_worker_is_separate_executable(monkeypatch, window):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(Path('C:/TubeDrop/TubeDrop.exe')))
    program, args = window.worker_command('identify', 'https://youtu.be/BaW_jenozKc')
    assert Path(program).name == 'TubeDropWorker.exe'
    assert args[0] == 'identify'
