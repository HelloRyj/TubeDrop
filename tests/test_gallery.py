import json
import pytest
from core import normalize_url
from douyin import parse_share_page

ID = '7616399587141737704'
CLEAN = 'https://p3-sign.douyinpic.com/tos-cn-i-test/original.webp?sign=abc'
MARKED = 'https://p3-sign.douyinpic.com/marked.jpeg'


def gallery_page(images, **extra):
    item = {'aweme_id': ID, 'desc': '图集', 'author': {'nickname': '作者'},
            'images': images, **extra}
    return 'window._ROUTER_DATA = ' + json.dumps({'loaderData': {
        'video_(id)/page': {'videoInfoRes': {'item_list': [item]}}}})


@pytest.mark.parametrize('url', [f'https://www.douyin.com/note/{ID}',
                                 f'https://www.iesdouyin.com/share/note/{ID}/'])
def test_note_urls_keep_content_type(url):
    assert normalize_url(url) == f'https://www.douyin.com/note/{ID}'


def test_gallery_uses_original_fields_in_order_and_never_watermark_fallback():
    info = parse_share_page(gallery_page([
        {'url_list': [CLEAN], 'download_url_list': [MARKED]},
        {'origin_image': {'url_list': [CLEAN + '&page=2']},
         'owner_watermark_image': {'url_list': [MARKED]}},
    ]), ID)
    assert info['media_type'] == 'images'
    assert [p['urls'][0] for p in info['images']] == [CLEAN, CLEAN + '&page=2']
    assert info['formats'] == []


@pytest.mark.parametrize('image', [
    {'download_url_list': [MARKED]}, {'owner_watermark_image': {'url_list': [MARKED]}},
    {'url_list': ['http://p3.douyinpic.com/photo.jpg']},
    {'url_list': ['https://127.0.0.1/photo.jpg']},
    {'url_list': ['https://p3.douyinpic.com.evil.org/photo.jpg']},
    {'url_list': ['https://user:secret@p3.douyinpic.com/photo.jpg']},
])
def test_gallery_missing_clean_image_fails_instead_of_skipping_it(image):
    with pytest.raises(ValueError):
        parse_share_page(gallery_page([{'url_list': [CLEAN]}, image]), ID)


def test_nested_gallery_and_music_are_explicit():
    info = parse_share_page(gallery_page(None, image_post_info={'images': [
        {'display_image': {'url_list': [CLEAN]}}]}, music={
            'play_url': {'url_list': ['https://sf3-cdn-tos.douyinstatic.com/music.mp3']}}), ID)
    assert info['media_type'] == 'images'
    assert len(info['images']) == 1
    assert info['formats'][0]['vcodec'] == 'none'
    assert info['formats'][0]['format_note'] == '图集配乐'


def test_gallery_worker_identification_without_video_formats(monkeypatch, capsys):
    import os
    import worker
    info = parse_share_page(gallery_page([{'url_list': [CLEAN]}]), ID)
    monkeypatch.setattr(worker, 'extract_share_video', lambda *_: info)
    monkeypatch.setattr(os, 'getpgrp', os.getpid)
    assert worker.run(['identify', f'https://www.douyin.com/note/{ID}']) == 0
    events = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    summary = events[-1]['video']
    assert summary['media_type'] == 'images'
    assert summary['image_count'] == 1
    assert not summary['has_video'] and not summary['has_audio']
