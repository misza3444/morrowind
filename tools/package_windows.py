#!/usr/bin/env python3
"""Build a relocatable Windows ZIP from the verified runtime and game sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from setup import ROOT, TEMPLATE, engine_directory

PACKAGE_NAME = 'LowcaEcha-Windows-x64'


def build_launcher(destination, compiler=None):
    compiler = compiler or shutil.which('cl') or shutil.which('x86_64-w64-mingw32-gcc')
    if not compiler:
        raise RuntimeError('Packaging needs MSVC (Windows Developer Command Prompt) or x86_64-w64-mingw32-gcc (Linux)')
    source = ROOT/'packaging/windows/launcher.c'
    if Path(compiler).name.lower() in ('cl','cl.exe'):
        command=[compiler,'/nologo','/O2','/MT','/utf-8','/Fe:'+str(destination),str(source),
                 '/link','/SUBSYSTEM:WINDOWS','shell32.lib','user32.lib']
    else:
        command=[compiler,'-O2','-Wall','-Wextra','-municode','-mwindows','-static','-static-libgcc',
                 str(source),'-o',str(destination),'-lshell32','-luser32']
    with tempfile.TemporaryDirectory(prefix='echo-launcher-') as build_directory:
        subprocess.run(command,cwd=build_directory,check=True)


def build_package(destination, compiler=None):
    engine = engine_directory('windows')
    required = [engine/'openmw.exe', engine/'resources/vfs/builtin.omwscripts',
                engine/'msvcp140.dll',engine/'vcruntime140_1.dll',engine/'app-local-runtime.json',
                TEMPLATE/'game_template/data/template.omwgame',
                TEMPLATE/'example_animated_creature/data/landracer.omwaddon']
    for path in required:
        if not path.is_file():
            raise RuntimeError('Run tools/setup.py --platform windows first; missing: ' + str(path))
    destination = destination.resolve()
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='echo-package-',dir=destination.parent) as temporary:
        package = Path(temporary)/PACKAGE_NAME
        package.mkdir()
        for source,target in [(engine,'engine'),(TEMPLATE/'game_template/data','data/template'),
                (TEMPLATE/'example_animated_creature/data','data/creatures'),
                (ROOT/'game','data/game'),(ROOT/'tests/engine','data/tests')]:
            shutil.copytree(source,package/target)
        subprocess.run([sys.executable,str(ROOT/'tools/build_content.py'),'--output',str(package/'data/echo')],check=True)
        (package/'config').mkdir()
        shutil.copyfile(ROOT/'config/settings.cfg',package/'config/settings.cfg')
        build_launcher(package/'Graj.exe',compiler)
        for name in ('CZYTAJ.txt',):
            content=(ROOT/'packaging/windows'/name).read_text(encoding='utf-8')
            (package/name).write_bytes(content.replace('\n','\r\n').encode('utf-8'))
        licenses=package/'licenses'
        licenses.mkdir()
        for name,source in [('THIRD_PARTY.md',ROOT/'THIRD_PARTY.md'),('Example-Suite-LICENSE.txt',TEMPLATE/'LICENSE'),
                            ('Example-Suite-AUTHORS.md',TEMPLATE/'AUTHORS.md')]:
            shutil.copyfile(source,licenses/name)
        metadata=json.loads((ROOT/'dependencies.lock.json').read_text(encoding='utf-8'))
        (package/'dependencies.lock.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
        # Record every shipped file; never include local saves, logs, Git metadata or downloads.
        hashes={}
        for path in sorted(package.rglob('*')):
            if path.is_file():
                with path.open('rb') as source:
                    hashes[path.relative_to(package).as_posix()]=hashlib.file_digest(source,'sha256').hexdigest()
        (package/'manifest.json').write_text(json.dumps({'platform':'windows-x64','files':hashes},indent=2)+'\n',encoding='utf-8')
        archive=Path(temporary)/destination.name
        with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as output:
            for path in sorted(package.rglob('*')):
                if path.is_file():
                    output.write(path,PACKAGE_NAME+'/'+path.relative_to(package).as_posix())
        archive.replace(destination)
    with destination.open('rb') as source:
        checksum=hashlib.file_digest(source,'sha256').hexdigest()
    destination.with_suffix(destination.suffix+'.sha256').write_text(checksum+'  '+destination.name+'\n',encoding='ascii')
    print('Windows ZIP:',destination,flush=True)
    print('SHA256:',checksum,flush=True)
    return destination


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist'/f'{PACKAGE_NAME}.zip')
    parser.add_argument('--compiler',help='Path to cl.exe or x86_64-w64-mingw32-gcc')
    args=parser.parse_args()
    build_package(args.output,args.compiler)


if __name__=='__main__':
    main()
