"""将已校验的官方 Windows 运行时及 wheels 打包为 NSIS 安装器。"""
import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from version import VERSION


def extract_archive(source, target):
    with zipfile.ZipFile(source) as archive:
        for entry in archive.infolist():
            if not (target / entry.filename).resolve().is_relative_to(target.resolve()):
                raise ValueError('压缩包包含越界路径。')
        archive.extractall(target)


def prepare_payload(source_root, cache, manifest, runtime_manifest, payload):
    payload.mkdir(parents=True, exist_ok=True)
    runtime = payload / 'runtime'
    site = runtime / 'Lib' / 'site-packages'
    site.mkdir(parents=True, exist_ok=True)
    for item in [*manifest, *runtime_manifest.values()]:
        name = item.get('filename') or item['file']
        path = cache / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'校验失败：{name}')
    extract_archive(cache / runtime_manifest['python']['file'], runtime)
    for item in manifest:
        extract_archive(cache / item['filename'], site)
    # 完全隔离于系统 Python；应用与第三方包只从安装目录加载。
    (runtime / 'python314._pth').write_text('python314.zip\n.\nLib/site-packages\n../app\nimport site\n', encoding='utf-8')
    app = payload / 'app'
    app.mkdir(exist_ok=True)
    for name in ('app.py', 'ui.py', 'core.py', 'worker.py', 'douyin.py', 'winjob.py',
                 'windows_launcher.py', 'version.py', 'icon.png', 'icon.ico', 'README.md', 'THIRD_PARTY.md'):
        shutil.copy2(source_root / name, app / name)
    binary_dir = payload / 'bin'
    binary_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(cache / runtime_manifest['node']['file']) as node:
        entry = next(name for name in node.namelist() if name.endswith('/node.exe'))
        (binary_dir / 'node.exe').write_bytes(node.read(entry))
    (payload / 'dependencies.json').write_text(json.dumps(
        {'wheels': manifest, 'runtimes': runtime_manifest}, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--runtimes', type=Path, required=True)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--makensis', default='makensis')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    prepare_payload(root, args.cache, json.loads(args.manifest.read_text()),
                    json.loads(args.runtimes.read_text()), args.payload)
    output = root.parent / f'TubeDrop-{VERSION}-Windows-x64-Setup.exe'
    subprocess.run([args.makensis, '-V3', f'-DPAYLOAD={args.payload.resolve()}',
                    f'-DOUTPUT={output}', f'-DVERSION={VERSION}', str(root / 'installer' / 'windows.nsi')], check=True)
    print(f'Windows 安装包已生成：{output}')


if __name__ == '__main__':
    main()
