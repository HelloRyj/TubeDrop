"""图集按顺序保存；外部地址逐跳校验，全部成功才发布目录。"""
from __future__ import annotations

import shutil
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urljoin

from douyin import IMAGE_HOSTS, MOBILE_UA, media_url_allowed

IMAGE_FORMATS = {'original', 'jpg', 'png', 'webp'}
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000


def fetch_image(session, url: str, destination: Path, proxy: str, progress=None):
    started = time.monotonic()
    for _ in range(5):
        if not media_url_allowed(url, IMAGE_HOSTS):
            raise ValueError('图片地址或跳转目标不是受支持的平台 HTTPS 地址。')
        response = session.get(url, allow_redirects=False, stream=True, timeout=30,
                               proxy=proxy or None)
        try:
            if response.status_code in {301, 302, 303, 307, 308}:
                url = urljoin(url, response.headers.get('Location') or '')
                continue
            if response.status_code != 200:
                raise ValueError(f'图片服务器返回 {response.status_code}。')
            total = int(response.headers.get('Content-Length') or 0)
            if total > MAX_IMAGE_BYTES:
                raise ValueError('图片超过 64 MB 安全上限。')
            size = 0
            with destination.open('wb') as target:
                for chunk in response.iter_content():
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES or time.monotonic() - started > 60:
                        raise ValueError('图片过大或下载超时，请重试。')
                    target.write(chunk)
                    if progress:
                        progress(size, total)
            if size == 0 or (total and total != size):
                raise ValueError('图片文件不完整。')
            return
        finally:
            response.close()
    raise ValueError('图片跳转次数过多。')


def read_image(path: Path):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImageReader
    QImageReader.setAllocationLimit(192)
    reader = QImageReader(str(path))
    # Qt WebP 探测需要 40 字节；极小的合法无损 WebP 可能只有 38 字节。
    # 仅在解码缓冲区补齐，不更改原图文件或其 RIFF 长度。
    if path.stat().st_size < 40:
        data = path.read_bytes()
        if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
            buffer = QBuffer()
            buffer.setData(QByteArray(data.ljust(40, b'\0')))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            reader = QImageReader(buffer)
    reader.setAutoTransform(True)
    kind = bytes(reader.format()).decode('ascii', errors='replace').lower()
    size = reader.size()
    if kind not in {'jpeg', 'png', 'webp', 'avif', 'heif'} or (
            size.width() <= 0 or size.height() <= 0
            or size.width() * size.height() > MAX_IMAGE_PIXELS):
        raise ValueError('图片格式无效、不受支持或像素尺寸过大。')
    image = reader.read()
    if image.isNull():
        raise ValueError('图片解码失败，文件可能不完整。')
    return image, 'jpg' if kind == 'jpeg' else kind


def save_image(source: Path, stem: Path, output_format: str) -> Path:
    from PySide6.QtGui import QColor, QImage, QPainter
    image, original_format = read_image(source)
    target = stem.with_suffix('.' + (original_format if output_format == 'original' else output_format))
    if output_format == 'original':
        shutil.copyfile(source, target)
    else:
        if output_format == 'jpg' and image.hasAlphaChannel():
            # JPEG 没有透明通道，使用白色背景，避免透明区域变黑。
            background = QImage(image.size(), QImage.Format.Format_RGB32)
            background.fill(QColor('white'))
            painter = QPainter(background)
            painter.drawImage(0, 0, image)
            painter.end()
            image = background
        # Qt WebP quality=100 使用无损编码；PNG 本身是无损格式。
        quality = {'jpg': 95, 'webp': 100, 'png': -1}[output_format]
        if not image.save(str(target), output_format.upper(), quality):
            raise ValueError('图片格式转换失败。')
    return target


def download_gallery(info: dict, folder: Path, output_format: str, proxy: str = '',
                     emit=lambda *_args, **_kwargs: None, *, session=None) -> dict:
    from curl_cffi import requests
    from yt_dlp.utils import sanitize_filename
    if output_format not in IMAGE_FORMATS:
        raise ValueError('图集请选择原格式、JPG、PNG 或 WebP。')
    photos = info.get('images') or []
    if not photos or len(photos) > 200:
        raise ValueError('未找到有效图片列表。')
    if session is None:
        with requests.Session(impersonate='safari_ios', headers={
                'User-Agent': MOBILE_UA, 'Referer': 'https://www.douyin.com/'}) as guest:
            return download_gallery(info, folder, output_format, proxy, emit, session=guest)
    name = sanitize_filename(str(info.get('title') or '抖音图集'), restricted=False)
    name = name.encode('utf-8')[:120].decode('utf-8', errors='ignore')
    identity = sanitize_filename(str(info.get('id') or 'images'), restricted=True)[:25]
    target = folder / f'{name} [{identity}]-{uuid.uuid4().hex[:8]}'
    names = []
    with tempfile.TemporaryDirectory(prefix='.TubeDrop-', dir=folder) as staging:
        staging = Path(staging)
        for index, photo in enumerate(photos):
            source = staging / 'source.part'
            last_emit = 0.0
            def progress(size, total):
                nonlocal last_emit
                now = time.monotonic()
                if now - last_emit >= 0.2:
                    fraction = min(size / total, 0.99) if total > 0 else 0
                    emit('progress', phase='images', percent=(index + fraction) / len(photos) * 100,
                         image_index=index + 1, image_count=len(photos))
                    last_emit = now
            for url in photo['urls'][:3]:
                try:
                    fetch_image(session, url, source, proxy, progress)
                    saved = save_image(source, staging / f'{index + 1:03d}', output_format)
                    break
                except (ValueError, requests.exceptions.RequestException):
                    source.unlink(missing_ok=True)
            else:
                raise ValueError(f'第 {index + 1} 张图片下载失败，未保存不完整图集。请重试。')
            names.append(saved.name)
            source.unlink(missing_ok=True)
            emit('progress', phase='images', percent=(index + 1) / len(photos) * 100,
                 image_index=index + 1, image_count=len(photos))
        if target.exists():
            raise ValueError('目标目录已存在，请重新下载。')
        staging.rename(target)
    return {'path': str(target), 'paths': [str(target / name) for name in names],
            'output_format': output_format, 'media_type': 'images', 'image_count': len(names)}
