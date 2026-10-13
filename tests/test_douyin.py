import pytest

from core import human_error, normalize_url, platform_name, thumbnail_url_allowed
from worker import resolve_video_url

VIDEO = 'https://www.douyin.com/video/6961737553342991651'


@pytest.mark.parametrize('raw', [
    VIDEO, VIDEO + '?tracking=1', 'douyin.com/video/6961737553342991651/',
    'https://www.iesdouyin.com/share/video/6961737553342991651/?region=CN',
    'https://www.douyin.com/?modal_id=6961737553342991651',
    'https://www.douyin.com/user/MS4wLjAB?modal_id=6961737553342991651',
    '分享视频\n' + VIDEO + ' 复制后打开抖音',
])
def test_douyin_video_links_are_canonical(raw):
    assert normalize_url(raw) == VIDEO
    assert platform_name(normalize_url(raw)) == '抖音'


@pytest.mark.parametrize('raw', [
    'https://douyin.com.evil.org/video/6961737553342991651',
    'https://www.douyin.com/user/creator',
    'https://www.douyin.com/note/6961737553342991651',
    'https://live.douyin.com/12345',
    'https://v.douyin.com/abc/extra',
    'https://user:pass@v.douyin.com/ABc1234/',
    VIDEO + '\nhttps://youtu.be/BaW_jenozKc',
    'https://www.douyin.com/?modal_id=6961737553342991651&modal_id=6961737553342991652',
])
def test_douyin_rejects_non_video_and_unsafe_links(raw):
    with pytest.raises(ValueError):
        normalize_url(raw)


class Response:
    status_code = 302
    def __init__(self, location):
        self.headers = {'Location': location}
        self.closed = False

    def raise_for_status(self):
        pass

    def close(self):
        self.closed = True


def test_douyin_share_link_resolves_and_closes_response():
    response = Response('https://www.iesdouyin.com/share/video/6961737553342991651/?tracking=1')
    assert resolve_video_url('https://v.douyin.com/ABc1234/', fetch=lambda _: response) == VIDEO
    assert response.closed


@pytest.mark.parametrize('destination', [
    'https://www.tiktok.com/@creator/video/6748451240264420610',
    'https://www.douyin.com/user/creator', 'http://127.0.0.1/private',
])
def test_douyin_share_link_rejects_destination_before_next_request(destination):
    calls = []
    def fetch(url):
        calls.append(url)
        return Response(destination)
    with pytest.raises(ValueError):
        resolve_video_url('https://v.douyin.com/ABc1234/', fetch=fetch)
    assert calls == ['https://v.douyin.com/ABc1234/']


def test_douyin_thumbnail_domains():
    assert thumbnail_url_allowed('https://p3.douyinpic.com/image.jpeg')
    assert thumbnail_url_allowed('https://p3-sign.douyinpic.com/image.jpeg')
    assert thumbnail_url_allowed('https://p3.douyincdn.com/image.jpeg')
    assert not thumbnail_url_allowed('https://douyinpic.com.evil.org/image.jpeg')


def test_douyin_cookie_error_is_actionable():
    message = human_error('Fresh cookies (not necessarily logged in) are needed', '抖音')
    assert '解析未成功' in message and '接口变化或访问限制' in message
    assert 'Cookie' not in message and '选择' not in message
