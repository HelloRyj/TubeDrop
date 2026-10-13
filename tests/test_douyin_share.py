import json

import pytest
import yt_dlp

from douyin import parse_share_page, extract_share_video
from worker import extract_video_info

VIDEO_ID = '6961737553342991651'
URL = f'https://www.douyin.com/video/{VIDEO_ID}'
PLAY = 'https://aweme.snssdk.com/aweme/v1/playwm/?video_id=example&ratio=720p'


def page(item=None):
    if item is None:
        item = {'aweme_id': VIDEO_ID, 'desc': '中文 {标题} "测试"',
                'author': {'nickname': '作者'},
                'video': {'play_addr': {'url_list': [PLAY]}, 'duration': 12500,
                          'height': 1920, 'width': 1080, 'bit_rate': None}}
    data = {'loaderData': {'video_(id)/page': {'videoInfoRes': {'item_list': [item]}}}}
    return '<script>window._ROUTER_DATA = ' + json.dumps(data) + ';</script>'


def test_share_page_extracts_matching_video_without_guessing_stream_resolution():
    info = parse_share_page(page(), VIDEO_ID)
    assert info['id'] == VIDEO_ID
    assert info['title'] == '中文 {标题} "测试"'
    assert info['duration'] == 12.5
    assert info['uploader'] == '作者'
    assert info['formats'][0]['url'] == PLAY
    assert not info['formats'][0].get('height')
    assert info['formats'][0]['acodec'] != 'none'


@pytest.mark.parametrize('html', [
    '<html>打开 App</html>',
    '<script>window._ROUTER_DATA = {broken};</script>',
    '<script>window._ROUTER_DATA = null;</script>',
    '<script>window._ROUTER_DATA = {"loaderData": []};</script>',
    page({'aweme_id': '123', 'video': {'play_addr': {'url_list': [PLAY]}}}),
    page({'aweme_id': VIDEO_ID, 'images': [{'uri': 'photo'}]}),
])
def test_empty_malformed_or_different_work_never_becomes_a_download(html):
    with pytest.raises(ValueError):
        parse_share_page(html, VIDEO_ID)


@pytest.mark.parametrize('url', [
    'http://aweme.snssdk.com/video.mp4', 'https://127.0.0.1/video.mp4',
    'https://aweme.snssdk.com.evil.org/video.mp4',
    'https://user:pass@aweme.snssdk.com/video.mp4',
    'https://aweme.snssdk.com:8443/video.mp4', 'file:///etc/passwd',
])
def test_share_page_rejects_unsafe_media(url):
    with pytest.raises(ValueError):
        parse_share_page(page({'aweme_id': VIDEO_ID,
                              'video': {'play_addr': {'url_list': [url]}}}), VIDEO_ID)


class Response:
    status_code = 200

    def __init__(self, html):
        self.html = html
        self.closed = False

    def iter_content(self):
        yield self.html.encode()

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, **options):
        self.calls.append((url, options))
        return self.responses[len(self.calls) - 1]


def test_empty_first_visit_retries_in_same_guest_session():
    responses = [Response('<html>打开 App</html>'), Response(page())]
    session = Session(responses)
    info = extract_share_video(URL, session=session)
    assert info['id'] == VIDEO_ID
    assert len(session.calls) == 2
    assert all(response.closed for response in responses)
    assert all(options['allow_redirects'] is False for _, options in session.calls)


def test_share_page_retries_are_bounded():
    session = Session([Response('<html>打开 App</html>') for _ in range(4)])
    with pytest.raises(ValueError, match='未能获取'):
        extract_share_video(URL, session=session)
    assert len(session.calls) == 4


def test_share_page_does_not_follow_redirects():
    response = Response('')
    response.status_code = 302
    session = Session([response] * 4)
    with pytest.raises(ValueError):
        extract_share_video(URL, session=session)
    assert all('douyin.com/share/video/' in url for url, _ in session.calls)


def test_oversized_page_is_closed_and_never_parsed(monkeypatch):
    monkeypatch.setattr('douyin.MAX_PAGE_BYTES', 32)
    responses = [Response('x' * 33) for _ in range(4)]
    with pytest.raises(ValueError, match='未能获取'):
        extract_share_video(URL, session=Session(responses))
    assert all(response.closed for response in responses)


def test_guest_request_honors_proxy_and_timeout():
    session = Session([Response(page())])
    extract_share_video(URL, 'http://127.0.0.1:7890', session=session)
    options = session.calls[0][1]
    assert options['proxy'] == 'http://127.0.0.1:7890'
    assert options['timeout'] == 20


def test_worker_uses_share_page_after_upstream_douyin_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise yt_dlp.utils.DownloadError('Fresh cookies are needed')
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', fail)
    monkeypatch.setattr('worker.extract_share_video', lambda *_: parse_share_page(page(), VIDEO_ID))
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = extract_video_info(ydl, URL)
    assert info['id'] == VIDEO_ID
    assert info['formats'][0]['url'] == PLAY


def test_other_platform_failures_do_not_call_douyin(monkeypatch):
    def fail(*args, **kwargs):
        raise yt_dlp.utils.DownloadError('network')
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', fail)
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        with pytest.raises(yt_dlp.utils.DownloadError):
            extract_video_info(ydl, 'https://youtu.be/jNQXAC9IVRw')
