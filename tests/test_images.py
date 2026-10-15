from pathlib import Path
import pytest
from PySide6.QtGui import QColor, QImage, QImageReader
from images import download_gallery, fetch_image, read_image
from test_gallery import CLEAN


class Response:
    status_code = 200
    headers = {}
    def __init__(self, content=b'', status=200, headers=None):
        self.content, self.status_code = content, status
        self.headers = headers or {}
        self.closed = False
    def iter_content(self):
        yield self.content
    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def image_bytes(tmp_path):
    image = QImage(24, 32, QImage.Format.Format_RGB32)
    image.fill(QColor('#3477ab'))
    image.setPixelColor(10, 10, QColor('#fde456'))
    path = tmp_path / 'fixture.png'
    assert image.save(str(path), 'PNG')
    return path.read_bytes()


@pytest.mark.parametrize('fmt', ['original', 'jpg', 'png', 'webp'])
def test_gallery_download_preserves_order_pixels_and_real_format(tmp_path, fmt):
    content = image_bytes(tmp_path)
    folder = tmp_path / 'downloads'; folder.mkdir()
    session = Session([Response(content), Response(content)])
    events = []
    info = {'id': '123', 'title': '../../标题', 'images': [{'urls': [CLEAN]}] * 2}
    result = download_gallery(info, folder, fmt, emit=lambda *a, **kw: events.append(kw), session=session)
    files = result['paths']
    assert len(files) == 2
    for i, value in enumerate(files, 1):
        path = Path(value)
        assert path.is_relative_to(folder)
        assert path.name == f'{i:03d}.' + ('png' if fmt == 'original' else fmt)
        reader = QImageReader(str(path))
        assert bytes(reader.format()).decode() == ('jpeg' if fmt == 'jpg' else 'png' if fmt == 'original' else fmt)
        image = reader.read()
        assert image.size().width() == 24 and image.size().height() == 32
        if fmt != 'jpg':
            assert image.pixelColor(0, 0) == QColor('#3477ab')
        if fmt == 'original':
            assert path.read_bytes() == content
    assert events[-1]['percent'] == 100
    assert not list(folder.glob('.TubeDrop-*'))


def test_failed_later_image_does_not_publish_partial_gallery(tmp_path):
    session = Session([Response(image_bytes(tmp_path)), Response(b'not an image')])
    folder = tmp_path / 'downloads'; folder.mkdir()
    info = {'id': '123', 'title': '标题', 'images': [{'urls': [CLEAN]}] * 2}
    with pytest.raises(ValueError):
        download_gallery(info, folder, 'original', session=session)
    assert list(folder.iterdir()) == []


def test_redirect_to_private_address_is_rejected_and_response_closed(tmp_path):
    response = Response(status=302, headers={'Location': 'http://127.0.0.1/private'})
    session = Session([response])
    with pytest.raises(ValueError):
        fetch_image(session, CLEAN, tmp_path / 'download', '')
    assert response.closed
    assert len(session.calls) == 1


def test_oversized_response_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr('images.MAX_IMAGE_BYTES', 10)
    response = Response(b'x' * 11)
    with pytest.raises(ValueError):
        fetch_image(Session([response]), CLEAN, tmp_path / 'download', '')
    assert response.closed


def test_tiny_lossless_webp_decodes_without_modifying_original(tmp_path):
    image = QImage(24, 32, QImage.Format.Format_RGB32)
    image.fill(QColor('#3477ab'))
    path = tmp_path / 'tiny.webp'
    assert image.save(str(path), 'WEBP', 100)
    original = path.read_bytes()
    decoded, kind = read_image(path)
    assert kind == 'webp' and decoded == image
    assert path.read_bytes() == original


def test_repeated_downloads_never_overwrite_and_keep_transparency(tmp_path):
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(QColor(20, 40, 60, 100))
    fixture = tmp_path / 'alpha.png'; assert image.save(str(fixture))
    info = {'id': '123', 'title': '🍵' * 300, 'images': [{'urls': [CLEAN]}]}
    folder = tmp_path / 'saved'; folder.mkdir()
    results = [download_gallery(info, folder, 'webp', session=Session([Response(fixture.read_bytes())]))
               for _ in range(2)]
    assert results[0]['path'] != results[1]['path']
    for result in results:
        path = Path(result['paths'][0])
        decoded, _ = read_image(path)
        assert decoded.pixelColor(0, 0) == image.pixelColor(0, 0)


def test_transparent_jpg_uses_white_background(tmp_path):
    from images import save_image
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    source = tmp_path / 'alpha.png'; assert image.save(str(source))
    result = save_image(source, tmp_path / 'converted', 'jpg')
    decoded, _ = read_image(result)
    assert decoded.pixelColor(5, 5).red() >= 250


def test_too_many_redirects_cannot_loop_forever(tmp_path):
    responses = [Response(status=302, headers={'Location': CLEAN}) for _ in range(5)]
    session = Session(responses)
    with pytest.raises(ValueError, match='跳转次数'):
        fetch_image(session, CLEAN, tmp_path / 'unused', '')
    assert len(session.calls) == 5 and all(r.closed for r in responses)
