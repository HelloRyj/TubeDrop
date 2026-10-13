"""抖音公开分享页解析；游客会话只保留在当前工作进程内。"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core import normalize_url, platform_name

MOBILE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) '
             'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 '
             'Mobile/15E148 Safari/604.1')
MAX_PAGE_BYTES = 2 * 1024 * 1024
MEDIA_HOSTS = ('snssdk.com', 'douyinvod.com', 'douyincdn.com', 'bytecdn.cn', 'ibytedtos.com')


def original_playback_url(url: str) -> str:
    parts = urlsplit(url)
    # 仅转换已验证的官方接口，避免破坏 CDN 签名或误改其他站点地址。
    if (parts.scheme != 'https' or parts.netloc != 'aweme.snssdk.com'
            or parts.path != '/aweme/v1/playwm/'):
        return url
    query = dict(parse_qsl(parts.query))
    if not re.fullmatch(r'[A-Za-z0-9_-]+', query.get('video_id', '')):
        return url
    query['ratio'] = '1080p'
    return urlunsplit((parts.scheme, parts.netloc, '/aweme/v1/play/', urlencode(query), ''))


def media_url_allowed(url):
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url)
        host = parts.hostname or ''
        return (parts.scheme == 'https' and not parts.username and not parts.password
                and parts.port in {None, 443}
                and any(host == domain or host.endswith('.' + domain) for domain in MEDIA_HOSTS))
    except ValueError:
        return False


def parse_share_page(html: str, video_id: str) -> dict:
    match = re.search(r'\bwindow\._ROUTER_DATA\s*=\s*', html)
    if not match:
        raise ValueError('分享页未返回作品数据。')
    try:
        # 只解析 JSON，不执行页面脚本；raw_decode 正确处理标题中的花括号。
        data, _ = json.JSONDecoder().raw_decode(html[match.end():])
        pages = data['loaderData'].values()
        item = next(item for page in pages if isinstance(page, dict)
                    for item in (page.get('videoInfoRes') or {}).get('item_list', [])
                    if isinstance(item, dict) and str(item.get('aweme_id')) == video_id)
        if item.get('images') or item.get('image_infos'):
            raise ValueError('此作品是图集，当前下载入口仅支持视频。')
        video = item['video']
        urls = (video.get('play_addr') or {}).get('url_list') or []
        urls = list(dict.fromkeys(original_playback_url(url) for url in urls if media_url_allowed(url)))
        if not urls:
            raise ValueError('分享页未返回可用的视频播放地址。')
        duration = video.get('duration')
        duration = duration / 1000 if isinstance(duration, (int, float)) and duration > 0 else None
        return {
            'id': video_id, 'title': item.get('desc') or f'抖音视频 {video_id}',
            'uploader': (item.get('author') or {}).get('nickname'), 'duration': duration,
            'thumbnail': next(iter((video.get('cover') or {}).get('url_list') or []), None),
            'extractor': 'douyin', 'extractor_key': 'Douyin',
            'webpage_url': f'https://www.douyin.com/video/{video_id}',
            'http_headers': {'User-Agent': MOBILE_UA, 'Referer': 'https://www.douyin.com/'},
            # 页面原始尺寸不一定等于播放流尺寸，不能冒充可下载的 1080p / 4K。
            'formats': [{'format_id': f'share-{index}', 'url': url, 'ext': 'mp4',
                         'vcodec': 'unknown', 'acodec': 'unknown',
                         'format_note': '原始播放视频'} for index, url in enumerate(urls)],
        }
    except (KeyError, TypeError, AttributeError, StopIteration, json.JSONDecodeError):
        raise ValueError('分享页未返回有效的作品数据。') from None


def extract_share_video(url: str, proxy: str = '', *, session=None) -> dict:
    url = normalize_url(url)
    if platform_name(url) != '抖音' or '/video/' not in url:
        raise ValueError('请使用抖音完整视频链接。')
    video_id = urlsplit(url).path.rsplit('/', 1)[-1]
    if session is None:
        from curl_cffi import requests
        with requests.Session(impersonate='safari_ios', headers={'User-Agent': MOBILE_UA}) as guest:
            return extract_share_video(url, proxy, session=guest)
    from curl_cffi.requests.exceptions import RequestException
    for host in ('www.douyin.com', 'www.iesdouyin.com'):
        # 首次访问可能只下发游客会话，第二次沿用此会话才能取得作品数据。
        for _ in range(2):
            response = None
            try:
                response = session.get(f'https://{host}/share/video/{video_id}/',
                                       proxy=proxy or None, timeout=20, stream=True,
                                       allow_redirects=False)
                if response.status_code != 200:
                    continue
                body = bytearray()
                for chunk in response.iter_content():
                    body.extend(chunk)
                    if len(body) > MAX_PAGE_BYTES:
                        raise ValueError('分享页数据过大。')
                return parse_share_page(body.decode('utf-8', errors='replace'), video_id)
            except (ValueError, RequestException):
                continue
            finally:
                if response is not None:
                    response.close()
    raise ValueError('未能获取抖音作品的播放地址，可能是解析接口变化、网络限制或作品不可用。请稍后重试。')
