"""构建当前 Mac 架构的独立 .app，捆绑下载和合并依赖。"""
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from core import runtime_path


def install_bundle(root):
    source = root / 'build' / 'dist' / 'TubeDrop.app'
    destination = root.parent / 'TubeDrop.app'
    backup = root / 'build' / 'previous-TubeDrop.app'
    # 保留 macOS 包中的符号链接，避免重复复制 Qt、Node 等运行库。
    if destination.exists():
        with (destination / 'Contents' / 'Info.plist').open('rb') as file:
            assert plistlib.load(file)['CFBundleIdentifier'] == 'local.tubedrop.desktop'
        if backup.exists():
            raise RuntimeError('备份目录已存在，请检查 build/previous-TubeDrop.app。')
        destination.rename(backup)
    try:
        shutil.copytree(source, destination, symlinks=True)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination)
        if backup.exists():
            backup.rename(destination)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def make_icon(root):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen
    icon = QImage(1024, 1024, QImage.Format.Format_ARGB32)
    icon.fill(Qt.GlobalColor.transparent)
    painter = QPainter(icon)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#226246'))
    painter.drawRoundedRect(QRectF(64, 64, 896, 896), 200, 200)
    painter.setPen(QPen(QColor('#f2f5e9'), 64, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(QPointF(512, 280), QPointF(512, 635))
    painter.drawLine(QPointF(360, 483), QPointF(512, 635))
    painter.drawLine(QPointF(512, 635), QPointF(664, 483))
    painter.drawLine(QPointF(320, 755), QPointF(704, 755))
    painter.end()
    icon.save(str(root / 'icon.png'))
    iconset = root / 'build' / 'TubeDrop.iconset'
    iconset.mkdir(parents=True, exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
            icon.scaled(size * scale, size * scale, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation).save(str(iconset / name))
    subprocess.run(['iconutil', '-c', 'icns', str(iconset), '-o', str(root / 'icon.icns')], check=True)


def main():
    root = Path(__file__).resolve().parent
    if sys.platform != 'darwin':
        raise SystemExit('此构建脚本用于 macOS。其他平台可从源码运行。')
    node = runtime_path('node')
    if not node:
        raise SystemExit('构建需要 Node.js 22+，用于捆绑 YouTube 解析运行环境。')
    make_icon(root)
    command = [
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
        '--name', 'TubeDrop', '--osx-bundle-identifier', 'local.tubedrop.desktop',
        '--target-architecture', 'arm64' if platform.machine() == 'arm64' else 'x86_64',
        '--icon', str(root / 'icon.icns'), '--add-data', f'{root / "icon.png"}:.',
        '--add-binary', f'{Path(node).resolve()}:bin',
        '--collect-all', 'yt_dlp', '--collect-all', 'yt_dlp_ejs',
        '--collect-all', 'imageio_ffmpeg', '--collect-all', 'certifi',
        '--copy-metadata', 'yt-dlp', '--copy-metadata', 'requests',
        '--distpath', str(root / 'build' / 'dist'), '--workpath', str(root / 'build' / 'temp'),
        '--specpath', str(root / 'build'), str(root / 'app.py'),
    ]
    subprocess.run(command, cwd=root, check=True)
    install_bundle(root)
    print(f'应用已生成：{root.parent / "TubeDrop.app"}')


if __name__ == '__main__':
    main()
