import pytest

from worker import load_user_cookies


def test_selected_cookie_file_is_read_in_memory_and_filtered(tmp_path):
    path = tmp_path / 'cookies.txt'
    content = ('# Netscape HTTP Cookie File\n'
               '.douyin.com\tTRUE\t/\tTRUE\t0\ts_v_web_id\tverify_sample\n'
               '.other.org\tTRUE\t/\tTRUE\t0\tsession\tother_sample\n')
    path.write_text(content)
    jar = load_user_cookies(str(path), '抖音')
    assert [cookie.name for cookie in jar] == ['s_v_web_id']
    assert jar.filename is None
    assert path.read_text() == content


@pytest.mark.parametrize('content', [
    '{"session": "sample_sensitive_value"}',
    '# Netscape HTTP Cookie File\ninvalid\tline\tsample_sensitive_value\n',
    '# Netscape HTTP Cookie File\n.douyin.com\tTRUE\t/\tTRUE\twrong\tname\tsample_sensitive_value\n',
])
def test_invalid_cookie_file_never_echoes_content(tmp_path, content, capsys):
    path = tmp_path / 'cookies.txt'
    path.write_text(content)
    with pytest.raises(ValueError, match='Cookie') as result:
        load_user_cookies(str(path), '抖音')
    assert 'sample_sensitive_value' not in str(result.value)
    assert 'sample_sensitive_value' not in capsys.readouterr().err


def test_missing_cookie_file_has_actionable_error(tmp_path):
    with pytest.raises(ValueError, match='Cookie'):
        load_user_cookies(str(tmp_path / 'missing.txt'), '抖音')


def test_cookie_from_other_platform_is_rejected(tmp_path):
    path = tmp_path / 'cookies.txt'
    path.write_text('# Netscape HTTP Cookie File\n.other.org\tTRUE\t/\tTRUE\t0\tsession\tsample\n')
    with pytest.raises(ValueError, match='抖音'):
        load_user_cookies(str(path), '抖音')


def test_worker_uses_selected_cookies_without_saving_or_logging_them(tmp_path, monkeypatch, capsys):
    import os
    import yt_dlp
    from worker import run
    content = '# Netscape HTTP Cookie File\n.douyin.com\tTRUE\t/\tTRUE\t0\ts_v_web_id\tverify_sample\n'
    path = tmp_path / 'cookies.txt'
    path.write_text(content)
    if os.name == 'posix':
        monkeypatch.setattr(os, 'getpgrp', os.getpid)
    else:
        monkeypatch.setattr('winjob.assign_worker_job', lambda: None)
    monkeypatch.setattr('worker.base_options', lambda *_: {'quiet': True})
    def identify(ydl, url, **kwargs):
        assert 'verify_sample' in ydl.cookiejar.get_cookie_header(url)
        assert ydl.params.get('cookiefile') is None
        return {'id': '6961737553342991651', 'extractor_key': 'Douyin',
                'formats': [{'height': 720, 'vcodec': 'avc1', 'acodec': 'aac'}]}
    monkeypatch.setattr(yt_dlp.YoutubeDL, 'extract_info', identify)
    assert run(['identify', 'https://www.douyin.com/video/6961737553342991651',
                '--cookies', str(path)]) == 0
    output = capsys.readouterr()
    assert 'verify_sample' not in output.out + output.err
    assert path.read_text() == content
