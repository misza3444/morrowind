#!/usr/bin/env python3
"""Install pinned upstream runtime/assets locally, without root or system changes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
ENGINE = RUNTIME / 'openmw-0.51.0-Linux-64Bit'
TEMPLATE = RUNTIME / 'example-suite'


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    lock = json.loads((ROOT / 'dependencies.lock.json').read_text())
    RUNTIME.mkdir(exist_ok=True)
    archive = RUNTIME / 'openmw.tar.gz'
    if not (ENGINE / 'openmw').exists():
        cached = Path('/workspace/.cache/echo-hunter/openmw-0.51.0-Linux-64Bit.tar.gz')
        if not archive.exists():
            if cached.exists():
                shutil.copyfile(cached, archive)
            else:
                temporary = archive.with_suffix('.partial')
                print('Downloading official OpenMW release...', flush=True)
                with urllib.request.urlopen(lock['openmw']['url'], timeout=90) as source:
                    with temporary.open('wb') as target:
                        shutil.copyfileobj(source, target)
                temporary.replace(archive)
        with archive.open('rb') as source:
            actual = hashlib.file_digest(source, 'sha256').hexdigest()
        if actual != lock['openmw']['sha256']:
            raise RuntimeError('OpenMW checksum mismatch; archive was not extracted')
        with tarfile.open(archive) as source:
            source.extractall(RUNTIME, filter='data')

    if not TEMPLATE.exists():
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1')
        run('git', 'clone', '--no-checkout', '--depth', '1', lock['template']['url'], str(TEMPLATE), env=env)
        run('git', '-C', str(TEMPLATE), 'fetch', '--depth', '1', 'origin', lock['template']['commit'], env=env)
        run('git', '-C', str(TEMPLATE), 'checkout', '--detach', lock['template']['commit'], env=env)
    head = subprocess.check_output(['git', '-C', str(TEMPLATE), 'rev-parse', 'HEAD'], text=True).strip()
    if head != lock['template']['commit']:
        raise RuntimeError('Template revision differs from the lock; existing files were preserved')
    run('git', '-C', str(TEMPLATE), 'lfs', 'install', '--local')
    run('git', '-C', str(TEMPLATE), 'lfs', 'pull', '--include=' + lock['template']['lfs_include'], '--exclude=')
    # Verify each materialized LFS file against its committed pointer.
    entries = subprocess.check_output(['git', '-C', str(TEMPLATE), 'lfs', 'ls-files', '--json'], text=True)
    count = 0
    for item in json.loads(entries)['files']:
        name = item['name']
        if not name.startswith(('game_template/data/', 'example_animated_creature/data/')):
            continue
        with (TEMPLATE / name).open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest != item['oid']:
            raise RuntimeError('Template LFS checksum mismatch: ' + name)
        count += 1
    print(f'Verified OpenMW {lock["openmw"]["version"]}; {count} template LFS assets.', flush=True)
    run('python3', str(ROOT / 'tools/build_content.py'))


if __name__ == '__main__':
    main()
