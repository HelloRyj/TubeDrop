import pytest
import yt_dlp
from worker import download_options, video_summary


def audio(codec, name, video=False):
    return {'format_id': name, 'url': f'https://media.example/{name}.mkv',
            'ext': 'mkv', 'acodec': codec, 'vcodec': 'h264' if video else 'none'}


@pytest.mark.parametrize('platform', ['YouTube', '抖音'])
@pytest.mark.parametrize('codec', ['flac', 'alac', 'pcm_s24le'])
def test_flac_prefers_lossless_original_track(tmp_path, platform, codec):
    combined = platform != 'YouTube'
    formats = [audio(codec, 'original', combined), audio('aac', 'lossy', combined)]
    if combined:
        formats.append(audio('flac', 'background-music'))
    with yt_dlp.YoutubeDL({'quiet': True, **download_options(tmp_path, None, 'flac', platform)}) as ydl:
        info = ydl.process_ie_result({'id': 'test', 'title': 'Test', 'extractor': 'test', 'formats': formats}, download=False)
    assert info['format_id'] == 'original'


def test_metadata_does_not_call_lossy_audio_lossless():
    info = {'id': 'test', 'formats': [audio('aac', 'a')], 'extractor_key': 'Youtube'}
    assert video_summary(info)['audio_quality'] == 'lossy'
    info['formats'] = [audio('flac', 'f')]
    assert video_summary(info)['audio_quality'] == 'lossless'
    info['formats'] = [audio('unknown', 'u')]
    assert video_summary(info)['audio_quality'] == 'unknown'


def test_flac_never_substitutes_music_for_silent_video(tmp_path):
    formats = [audio('none', 'silent', True), audio('flac', 'music')]
    with yt_dlp.YoutubeDL({'quiet': True, **download_options(tmp_path, None, 'flac', '抖音')}) as ydl:
        with pytest.raises(yt_dlp.utils.ExtractorError, match="Requested format"):
            ydl.process_ie_result({'id': 'test', 'title': 'Test', 'extractor': 'test', 'formats': formats}, download=False)


def test_youtube_lossless_audio_in_combined_video_is_preferred(tmp_path):
    formats = [audio('flac', 'combined', True), audio('aac', 'audio')]
    with yt_dlp.YoutubeDL({'quiet': True, **download_options(tmp_path, None, 'flac', 'YouTube')}) as ydl:
        info = ydl.process_ie_result({'id': 'test', 'title': 'Test', 'extractor': 'test', 'formats': formats}, download=False)
    assert info['format_id'] == 'combined'
