from urllib.parse import parse_qs, urlsplit

import pytest
import yt_dlp

from douyin import original_playback_url
from worker import original_video_formats, extract_video_info


def video(format_id='play', **extra):
    return {'format_id': format_id, 'url': 'https://media.example/video.mp4',
            'ext': 'mp4', 'vcodec': 'h264', 'acodec': 'aac', 'height': 720, **extra}


def test_douyin_playback_preserves_video_id_and_uses_original_endpoint():
    address = original_playback_url('https://aweme.snssdk.com/aweme/v1/playwm/?video_id=abc123&ratio=720p&line=0')
    parts = urlsplit(address)
    assert parts.path == '/aweme/v1/play/'
    assert parse_qs(parts.query) == {'video_id': ['abc123'], 'ratio': ['1080p'], 'line': ['0']}


@pytest.mark.parametrize('address', [
    'https://v3.douyinvod.com/signed/video.mp4?signature=abc&ratio=720p',
    'https://other.snssdk.com/aweme/v1/playwm/?video_id=abc',
    'https://aweme.snssdk.com/other/playwm/?video_id=abc',
])
def test_only_known_official_play_endpoint_is_rewritten(address):
    assert original_playback_url(address) == address


@pytest.mark.parametrize('platform', ['YouTube', 'TikTok', '抖音'])
@pytest.mark.parametrize('marked', [
    video('wm', format_note='Download video, watermarked'),
    video('wm', has_watermark=True),
    video('wm', url='https://aweme.snssdk.com/aweme/v1/playwm/?video_id=abc'),
])
def test_known_watermark_formats_are_removed_on_every_platform(platform, marked):
    clean = video()
    info = {'formats': [clean, marked], 'requested_downloads': [marked], 'url': marked['url']}
    result = original_video_formats(info, platform)
    assert result['formats'] == [clean]
    assert 'requested_downloads' not in result
    assert 'url' not in result
    assert info['formats'] == [clean, marked]


@pytest.mark.parametrize('platform', ['TikTok', '抖音'])
def test_no_playback_video_does_not_fall_back_to_watermark_or_music(platform):
    with pytest.raises(ValueError, match='原始播放源'):
        original_video_formats({'formats': [
            video('download'), video('audio', vcodec='none'),
        ]}, platform)


def test_youtube_separate_video_and_audio_are_preserved():
    formats = [video('137', acodec='none'), video('140', vcodec='none')]
    assert original_video_formats({'formats': formats}, 'YouTube')['formats'] == formats


def test_watermark_free_note_is_not_mistaken_for_watermarked():
    formats = [video(format_note='watermark-free playback')]
    assert original_video_formats({'formats': formats}, 'TikTok')['formats'] == formats


def test_worker_filters_before_selecting_resolution(monkeypatch):
    raw = {'id': '123', 'title': 'Test', 'formats': [
        video('play', height=720), video('download', height=1080, format_note='watermarked'),
    ]}
    def extract(*args, **kwargs):
        assert kwargs['process'] is False
        return raw
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', extract)
    with yt_dlp.YoutubeDL({'quiet': True, 'format': 'best'}) as ydl:
        info = extract_video_info(ydl, 'https://www.tiktok.com/@creator/video/7047596209028074758')
    assert info['format_id'] == 'play'
    assert [f['height'] for f in info['formats']] == [720]
