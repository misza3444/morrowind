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


def build_launcher(destination, compiler=None, source_name='launcher.c'):
    compiler = compiler or shutil.which('cl') or shutil.which('x86_64-w64-mingw32-gcc')
    if not compiler:
        raise RuntimeError('Packaging needs MSVC (Windows Developer Command Prompt) or x86_64-w64-mingw32-gcc (Linux)')
    source = ROOT/'packaging/windows'/source_name
    if Path(compiler).name.lower() in ('cl','cl.exe'):
        command=[compiler,'/nologo','/O2','/MT','/utf-8','/Fe:'+str(destination),str(source),
                 '/link','/SUBSYSTEM:WINDOWS','shell32.lib','user32.lib']
    else:
        command=[compiler,'-O2','-Wall','-Wextra','-municode','-mwindows','-static','-static-libgcc',
                 str(source),'-o',str(destination),'-lshell32','-luser32']
    with tempfile.TemporaryDirectory(prefix='echo-launcher-') as build_directory:
        subprocess.run(command,cwd=build_directory,check=True)


def compile_csharp(destination, sources, compiler=None, window=True):
    compiler = compiler or shutil.which('csc') or shutil.which('mcs')
    if not compiler:
        import os
        for framework in ('Framework64', 'Framework'):
            path = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Microsoft.NET'/framework/'v4.0.30319/csc.exe'
            if path.is_file():
                compiler = str(path)
                break
    if not compiler:
        raise RuntimeError('Building the updater needs .NET Framework csc (Windows) or Mono mcs (Linux)')
    mono = Path(compiler).name.lower() in ('mcs', 'mcs.exe')
    prefix = '-' if mono else '/'
    references = ['System.Core', 'System.Web.Extensions', 'System.IO.Compression',
                  'System.IO.Compression.FileSystem', 'System.Windows.Forms', 'System.Drawing']
    command = [compiler, prefix+'nologo', prefix+'langversion:5', prefix+'optimize+', prefix+'platform:x64',
               prefix+'target:'+('winexe' if window else 'exe'), prefix+'out:'+str(destination)]
    command += [prefix+'reference:'+name+'.dll' for name in references]
    command += [str(source) for source in sources]
    subprocess.run(command, check=True)


def content_id(files):
    content = ''.join(f'{item["path"]}\t{item["sha256"]}\t{item["size"]}\n' for item in sorted(files, key=lambda item:item['path']))
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def archive_files(destination, root, files, prefix=''):
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for name in sorted(files):
            info = zipfile.ZipInfo(prefix+name, date_time=(2020,1,1,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, (root/name).read_bytes(), compresslevel=6)


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def build_package(destination, compiler=None, csharp_compiler=None):
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
        package = Path(temporary)/'payload'
        package.mkdir()
        for source,target in [(engine,'engine'),(TEMPLATE/'game_template/data','data/template'),
                (TEMPLATE/'example_animated_creature/data','data/creatures'),
                (ROOT/'game','data/game'),(ROOT/'tests/engine','data/tests')]:
            shutil.copytree(source,package/target)
        subprocess.run([sys.executable,str(ROOT/'tools/build_content.py'),'--output',str(package/'data/echo')],check=True)
        (package/'config').mkdir()
        shutil.copyfile(ROOT/'config/settings.cfg',package/'config/settings.cfg')
        build_launcher(package/'Uruchom.exe',compiler)
        compile_csharp(package/'Aktualizuj.exe', [ROOT/'packaging/windows/UpdateCore.cs', ROOT/'packaging/windows/Updater.cs'], csharp_compiler)
        shutil.copyfile(ROOT/'packaging/windows/Aktualizuj.exe.config',package/'Aktualizuj.exe.config')
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
        files=[]
        for path in sorted(package.rglob('*')):
            if path.is_file():
                files.append({'path':path.relative_to(package).as_posix(), 'sha256':digest(path), 'size':path.stat().st_size})
        bundles=[]
        releases=Path(temporary)/'updates'
        releases.mkdir()
        for name in ('runtime','game'):
            selected=[item for item in files if item['path'].startswith(('engine/','data/template/','data/creatures/')) == (name=='runtime')]
            identifier=content_id(selected)
            preliminary=releases/(name+'.zip')
            archive_files(preliminary, package, [item['path'] for item in selected])
            archive_hash=digest(preliminary)
            asset=f'{name}-{archive_hash}.zip'
            preliminary.replace(releases/asset)
            bundles.append({'name':name, 'id':identifier, 'asset':asset, 'sha256':archive_hash,
                            'size':(releases/asset).stat().st_size, 'files':selected})
        version=hashlib.sha256(''.join(bundle['name']+'\t'+bundle['id']+'\n' for bundle in sorted(bundles,key=lambda item:item['name'])).encode('utf-8')).hexdigest()
        revision=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
        release={'schema':1, 'platform':'windows-x64', 'version':version, 'revision':revision,
                 'release_tag':'windows-'+version, 'bundles':bundles}
        manifest=json.dumps(release,indent=2)+'\n'
        (releases/'update.json').write_text(manifest,encoding='utf-8')
        (package/'version.json').write_text(manifest,encoding='utf-8')
        portable=Path(temporary)/PACKAGE_NAME
        (portable/'versions').mkdir(parents=True)
        installed=portable/'versions'/version[:32]
        shutil.move(str(package),installed)
        (portable/'bootstrap').mkdir()
        for name in ('Aktualizuj.exe','Aktualizuj.exe.config','Uruchom.exe'):
            shutil.copyfile(installed/name,portable/'bootstrap'/name)
        build_launcher(portable/'Graj.exe',compiler,'bootstrap.c')
        (portable/'current.txt').write_bytes((version[:32]+'\n').encode('ascii'))
        shutil.copyfile(installed/'CZYTAJ.txt',portable/'CZYTAJ.txt')
        archive=Path(temporary)/destination.name
        archive_files(archive,portable,[path.relative_to(portable).as_posix() for path in portable.rglob('*') if path.is_file()],PACKAGE_NAME+'/')
        # Drop-in bootstrap for an existing flat installation, or a first online install.
        bootstrap=Path(temporary)/'LowcaEcha-Launcher-Windows-x64.zip'
        archive_files(bootstrap,portable,['Graj.exe','bootstrap/Aktualizuj.exe','bootstrap/Aktualizuj.exe.config','bootstrap/Uruchom.exe','CZYTAJ.txt'])
        bootstrap.replace(destination.parent/bootstrap.name)
        (destination.parent/(bootstrap.name+'.sha256')).write_text(digest(destination.parent/bootstrap.name)+'  '+bootstrap.name+'\n',encoding='ascii')
        for path in releases.iterdir():
            path.replace(destination.parent/path.name)
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
    parser.add_argument('--csharp-compiler',help='Path to csc or mcs')
    args=parser.parse_args()
    build_package(args.output,args.compiler,args.csharp_compiler)


if __name__=='__main__':
    main()
