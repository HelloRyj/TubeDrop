import pytest

from core import thumbnail_url_allowed
from worker import resolve_video_url

VIDEO = 'https://www.tiktok.com/@creator/video/6748451240264420610'


class Response:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {'Location': location} if location else {}

    def close(self):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('HTTP error')


def test_short_link_resolves_to_tiktok_video():
    responses = iter([Response(302, 'https://www.tiktok.com/t/ZTRC5xgJp/'), Response(302, VIDEO + '?tracking=1')])
    assert resolve_video_url('https://vm.tiktok.com/ZM123Abcd/', fetch=lambda *_: next(responses)) == VIDEO


@pytest.mark.parametrize('redirect', [
    'https://evil.org/video/123', 'http://127.0.0.1/private',
    'https://youtube.com/watch?v=BaW_jenozKc',
    'https://www.tiktok.com/@creator',
    'https://www.tiktok.com.evil.org/@creator/video/6748451240264420610',
])
def test_short_link_rejects_external_or_non_video_redirect(redirect):
    calls = []
    def fetch(url):
        calls.append(url)
        return Response(302, redirect)
    with pytest.raises(ValueError):
        resolve_video_url('https://vm.tiktok.com/ZM123Abcd/', fetch=fetch)
    assert calls == ['https://vm.tiktok.com/ZM123Abcd/']


def test_short_link_loop_has_finite_attempts():
    calls = []
    def fetch(url):
        calls.append(url)
        return Response(302, '/ZM123Abcd/')
    with pytest.raises(ValueError, match='跳转'):
        resolve_video_url('https://vm.tiktok.com/ZM123Abcd/', fetch=fetch)
    assert len(calls) <= 5


def test_direct_link_does_not_make_extra_network_request():
    def fail(_):
        raise AssertionError('Direct links should not need short URL resolution')
    assert resolve_video_url(VIDEO, fetch=fail) == VIDEO


@pytest.mark.parametrize(('url', 'allowed'), [
    ('https://p16-sign-va.tiktokcdn.com/image.jpeg?signature=1', True),
    ('https://p16.tiktokcdn-us.com/image.jpeg', True),
    ('https://i.ytimg.com/vi/test/default.jpg', True),
    ('https://tiktokcdn.com.evil.org/image.jpeg', False),
    ('http://p16.tiktokcdn.com/image.jpeg', False),
    ('https://user:pass@p16.tiktokcdn.com/image.jpeg', False),
])
def test_tiktok_thumbnail_domain_allowlist(url, allowed):
    assert thumbnail_url_allowed(url) == allowed
