#!/usr/bin/env python3
"""Install checksum-verified OpenMW and pinned assets locally on Linux or Windows."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
TEMPLATE = RUNTIME / 'example-suite'


def platform_key(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if machine not in ('amd64', 'x86_64') or system not in ('Windows', 'Linux'):
        raise RuntimeError('Supported platforms: Windows x64 and Linux x86_64')
    return 'windows' if system == 'Windows' else 'linux'


def engine_directory(target=None):
    name = 'OpenMW-0.51.0-Windows-x64' if (target or platform_key()) == 'windows' else 'openmw-0.51.0-Linux-64Bit'
    return RUNTIME / name


def engine_binary(target=None):
    target = target or platform_key()
    return engine_directory(target) / ('openmw.exe' if target == 'windows' else 'openmw.x86_64')


ENGINE = engine_directory()


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def verify_file(path, expected):
    with path.open('rb') as source:
        actual = hashlib.file_digest(source, 'sha256').hexdigest()
    if actual != expected:
        raise RuntimeError(f'Checksum mismatch: {path.name}; the file was not used')


def download_checked(spec, destination):
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + '.partial')
        print('Downloading ' + destination.name + '...', flush=True)
        try:
            with urllib.request.urlopen(spec['url'], timeout=90) as source, temporary.open('wb') as target:
                shutil.copyfileobj(source, target)
            verify_file(temporary, spec['sha256'])
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    verify_file(destination, spec['sha256'])


def find_seven_zip(explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if path.is_file():
            return str(path)
        raise RuntimeError('7-Zip executable not found: ' + str(path))
    for command in ('7z', '7zz'):
        if path := shutil.which(command):
            return path
    for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
        if directory := os.environ.get(variable):
            path = Path(directory) / '7-Zip/7z.exe'
            if path.is_file():
                return str(path)
    raise RuntimeError('Install 7-Zip (Windows: winget install --id 7zip.7zip -e), or pass --seven-zip PATH')


def cabinet_payloads(data):
    """Read bounded CAB payloads, excluding their trailing Authenticode blocks."""
    offset = 0
    while True:
        start = data.find(b'MSCF', offset)
        if start < 0:
            return
        offset = start + 4
        if start + 36 > len(data):
            continue
        size = struct.unpack_from('<I', data, start + 8)[0]
        file_table = struct.unpack_from('<I', data, start + 16)[0]
        if data[start + 24:start + 26] == b'\x03\x01' and 36 <= file_table < size and start + size <= len(data):
            yield data[start:start + size]
            offset = start + size


def prepare_vc_runtime(engine, seven_zip):
    """Use the unchanged x64 DLLs in OpenMW's own Microsoft redistributable."""
    provenance = engine / 'app-local-runtime.json'
    if provenance.exists():
        recorded = json.loads(provenance.read_text(encoding='utf-8'))
        for name, digest in recorded['files'].items():
            verify_file(engine / name, digest)
        return
    redistributable = engine / 'redist/vc_redist.x64.exe'
    if not redistributable.is_file():
        raise RuntimeError('The official Windows runtime has no VC++ redistributable')
    found = {}
    with tempfile.TemporaryDirectory(prefix='vc-runtime-', dir=RUNTIME) as directory:
        temporary = Path(directory)
        for index, payload in enumerate(cabinet_payloads(redistributable.read_bytes())):
            cabinet = temporary / f'bundle-{index}.cab'
            cabinet.write_bytes(payload)
            outer = temporary / f'bundle-{index}'
            run(seven_zip, 'x', '-y', '-o' + str(outer), str(cabinet), stdout=subprocess.DEVNULL)
            for entry in outer.iterdir():
                if not entry.is_file():
                    continue
                data = entry.read_bytes()
                if not data.startswith(b'MSCF'):
                    continue
                for inner_index, content in enumerate(cabinet_payloads(data)):
                    inner = temporary / f'inner-{index}-{entry.name}-{inner_index}.cab'
                    inner.write_bytes(content)
                    listing = subprocess.check_output([seven_zip, 'l', '-slt', '-sccUTF-8', str(inner)], encoding='utf-8')
                    if 'Path = msvcp140.dll_amd64' not in listing:
                        continue
                    output = temporary / (inner.stem + '-files')
                    run(seven_zip, 'x', '-y', '-o' + str(output), str(inner), stdout=subprocess.DEVNULL)
                    for source in output.glob('*.dll_amd64'):
                        name = source.name.removesuffix('_amd64')
                        # Copy only the x64 files; preserve each signed DLL byte for byte.
                        shutil.copyfile(source, engine / name)
                        with source.open('rb') as stream:
                            found[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    if not {'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'} <= found.keys():
        raise RuntimeError('The pinned VC++ redistributable had no complete x64 runtime')
    with redistributable.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    provenance.write_text(json.dumps({'source': 'redist/vc_redist.x64.exe', 'source_sha256': digest,
                                     'files': found}, indent=2) + '\n', encoding='utf-8')


def install_engine(lock, target, seven_zip=None):
    engine = engine_directory(target)
    if engine_binary(target).exists():
        if target == 'windows':
            prepare_vc_runtime(engine, find_seven_zip(seven_zip))
        return engine
    if engine.exists():
        raise RuntimeError('Incomplete runtime directory; existing files preserved: ' + str(engine))
    spec = lock['openmw']['windows'] if target == 'windows' else lock['openmw']
    archive = RUNTIME / ('OpenMW-0.51.0-Windows-x64.exe' if target == 'windows' else 'openmw.tar.gz')
    if target == 'linux' and not archive.exists():
        cached = Path('/workspace/.cache/echo-hunter/openmw-0.51.0-Linux-64Bit.tar.gz')
        if cached.exists():
            shutil.copyfile(cached, archive)
    download_checked(spec, archive)
    with tempfile.TemporaryDirectory(prefix='openmw-extract-', dir=RUNTIME) as directory:
        temporary = Path(directory)
        if target == 'windows':
            # Extract the official NSIS payload; never run its administrator installer.
            run(find_seven_zip(seven_zip), 'x', '-y', '-o' + str(temporary), str(archive), stdout=subprocess.DEVNULL)
            for path in temporary.iterdir():
                if path.name.startswith('$'):
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
            if not (temporary / 'openmw.exe').is_file():
                raise RuntimeError('The Windows installer did not contain openmw.exe')
            prepare_vc_runtime(temporary, find_seven_zip(seven_zip))
            shutil.copytree(temporary, engine)
        else:
            with tarfile.open(archive) as source:
                source.extractall(temporary, filter='data')
            shutil.move(str(temporary / engine.name), engine)
    return engine


def verify_assets(lock):
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
    entries = subprocess.check_output(['git', '-C', str(TEMPLATE), 'lfs', 'ls-files', '--json'], text=True)
    count = 0
    for item in json.loads(entries)['files']:
        name = item['name']
        if name.startswith(('game_template/data/', 'example_animated_creature/data/')):
            verify_file(TEMPLATE / name, item['oid'])
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('linux', 'windows'), help='Also allows preparing a Windows ZIP from Linux')
    parser.add_argument('--seven-zip', help='Path to 7z/7zz, used to extract the Windows installer without running it')
    args = parser.parse_args()
    target = args.platform or platform_key()
    lock = json.loads((ROOT / 'dependencies.lock.json').read_text(encoding='utf-8'))
    RUNTIME.mkdir(exist_ok=True)
    install_engine(lock, target, args.seven_zip)
    count = verify_assets(lock)
    print(f'Prepared OpenMW {lock["openmw"]["version"]} ({target}); verified {count} template LFS assets.', flush=True)
    run(sys.executable, str(ROOT / 'tools/build_content.py'))


if __name__ == '__main__':
    main()
