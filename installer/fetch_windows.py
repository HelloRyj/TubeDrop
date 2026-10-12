"""下载锁定的 Windows 组件；分块重试，逐文件核对官方 SHA256。"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path

import requests


def download_file(item, cache):
    filename = item.get('filename') or item['file']
    target = cache / filename
    digest = item['sha256']
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return
    url = item['url']
    size = item.get('size')
    if not size:
        response = requests.head(url, allow_redirects=True, timeout=60)
        response.raise_for_status()
        size = int(response.headers['Content-Length'])
    count = 8 if size > 20_000_000 else 1
    chunk = (size + count - 1) // count

    def fetch(index):
        start, end = index * chunk, min(size - 1, (index + 1) * chunk - 1)
        part = cache / f'{filename}.{index}.part'
        if part.exists() and part.stat().st_size == end - start + 1:
            return part
        for attempt in range(5):
            try:
                address = url
                if attempt < 3 and url.startswith('https://files.pythonhosted.org'):
                    address = url.replace('https://files.pythonhosted.org', 'https://mirrors.aliyun.com/pypi')
                with requests.get(address, headers={'Range': f'bytes={start}-{end}'},
                                  stream=True, timeout=120) as response:
                    response.raise_for_status()
                    if response.status_code != 206 and count > 1:
                        raise RuntimeError('下载服务器未提供分块响应。')
                    with part.open('wb') as output:
                        for block in response.iter_content(262144):
                            output.write(block)
                if part.stat().st_size != end - start + 1:
                    raise RuntimeError('下载不完整。')
                return part
            except (requests.RequestException, RuntimeError):
                if attempt == 4:
                    raise
    with ThreadPoolExecutor(max_workers=count) as pool:
        parts = list(pool.map(fetch, range(count)))
    with target.open('wb') as output:
        for part in parts:
            output.write(part.read_bytes())
    if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        raise RuntimeError(f'SHA256 校验失败：{filename}')
    print(f'已校验：{filename}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    wheels = json.loads((root / 'windows-manifest.json').read_text())
    runtimes = json.loads((root / 'windows-runtime-manifest.json').read_text())
    python = runtimes['python']
    python['url'] = f'https://www.python.org/ftp/python/{python["version"]}/{python["file"]}'
    node = runtimes['node']
    node['url'] = f'https://nodejs.org/dist/{node["version"]}/{node["file"]}'
    # 连接数仅用于构建依赖下载，与视频下载速度无关。
    for item in [*wheels, python, node]:
        download_file(item, args.cache)


if __name__ == '__main__':
    main()
