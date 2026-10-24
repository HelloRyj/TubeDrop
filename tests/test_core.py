import pytest

from core import normalize_url, available_heights, format_selector, human_error


@pytest.mark.parametrize('url', [
    'https://www.youtube.com/watch?v=BaW_jenozKc&list=ignored',
    'https://youtu.be/BaW_jenozKc?si=tracking',
    'youtube.com/shorts/BaW_jenozKc',
    'https://m.youtube.com/embed/BaW_jenozKc',
    ' https://music.youtube.com/watch?v=BaW_jenozKc ',
])
def test_normalize_video_links(url):
    assert normalize_url(url) == 'https://www.youtube.com/watch?v=BaW_jenozKc'


@pytest.mark.parametrize('url', [
    '', 'https://evil.youtube.com/watch?v=BaW_jenozKc',
    'https://youtube.com.evil.org/watch?v=BaW_jenozKc',
    'https://youtube.com@evil.org/watch?v=BaW_jenozKc',
    'https://user:pass@youtube.com/watch?v=BaW_jenozKc',
    'https://youtube.com:444/watch?v=BaW_jenozKc',
    'file:///etc/passwd', 'https://youtube.com/playlist?list=123',
    'https://youtube.com/watch?v=../foo',
    'https://youtu.be/BaW_jenozKc/extra',
])
def test_reject_non_video_or_untrusted_links(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_quality_ignores_audio_and_storyboards():
    formats = [
        {'height': 1080, 'vcodec': 'avc1'},
        {'height': 720, 'vcodec': 'vp9'},
        {'height': 720, 'vcodec': 'avc1'},
        {'height': 90, 'vcodec': 'none'},
        {'vcodec': 'none'},
    ]
    assert available_heights(formats) == [1080, 720]


def test_quality_fallback_always_keeps_resolution_cap():
    selector = format_selector(720)
    assert all('height<=720' in branch for branch in selector.split('/'))
    assert format_selector(None) == 'bv*+ba/b'


def test_invalid_quality_rejected():
    with pytest.raises(ValueError):
        format_selector(-10)


def test_network_error_is_actionable():
    assert '网络' in human_error('Unable to download webpage: timed out')
    assert '登录' in human_error('Sign in to confirm you’re not a bot')


@pytest.mark.parametrize('raw', [
    'https://www.tiktok.com/@creator/video/6748451240264420610?is_from_webapp=1',
    'tiktok.com/@creator.name/video/6748451240264420610',
    'https://m.tiktok.com/@creator/video/6748451240264420610',
    'https://www.tiktok.com/share/video/6748451240264420610/',
    'https://www.tiktok.com/embed/6748451240264420610',
    'https://vm.tiktok.com/ZM123Abcd/?share=1',
    'https://vt.tiktok.com/ZSe4FqkKd/',
    'https://www.tiktok.com/t/ZTRC5xgJp/',
    '分享作品 https://vm.tiktok.com/ZM123Abcd/ 复制打开',
])
def test_removed_tiktok_links_are_rejected(raw):
    with pytest.raises(ValueError, match='YouTube.*抖音'):
        normalize_url(raw)


@pytest.mark.parametrize('url', [
    'https://evil.tiktok.com/@creator/video/6748451240264420610',
    'https://tiktok.com.evil.org/@creator/video/6748451240264420610',
    'https://www.tiktok.com/@creator',
    'https://www.tiktok.com/@creator/live',
    'https://www.tiktok.com/@creator/photo/6748451240264420610',
    'https://www.tiktok.com/@creator/video/../../secret',
    'https://vm.tiktok.com/ZM123Abcd/extra',
    'https://vt.tiktok.com/?url=https://evil.org',
    'https://user:pass@www.tiktok.com/@creator/video/6748451240264420610',
])
def test_reject_invalid_tiktok_links(url):
    with pytest.raises(ValueError):
        normalize_url(url)
