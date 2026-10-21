#!/usr/bin/env python3
"""Publish verified bundles first, then advance the public launcher feed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from package_windows import ROOT, digest

REPOSITORY='misza3444/morrowind'


def gh(*arguments, capture=False, check=True):
    return subprocess.run(['gh',*arguments,'--repo',REPOSITORY] if arguments[0]=='release' else ['gh',*arguments],
                          check=check,text=True,capture_output=capture)


def main():
    directory=ROOT/'dist'
    release=json.loads((directory/'update.json').read_text(encoding='utf-8'))
    revision=os.environ['GITHUB_SHA']
    head=gh('api',f'repos/{REPOSITORY}/commits/main','--jq','.sha',capture=True).stdout.strip()
    if revision != head:
        print('A newer main commit exists; this build will not replace the update channel.')
        return
    if release['revision'] != revision:
        raise RuntimeError('Release metadata does not match this workflow commit')
    bundles=[]
    for bundle in release['bundles']:
        path=directory/bundle['asset']
        if path.stat().st_size != bundle['size'] or digest(path) != bundle['sha256']:
            raise RuntimeError('Bundle checksum differs from the release metadata')
        bundles.append(path)
    archive=directory/'LowcaEcha-Windows-x64.zip'
    if digest(archive) != archive.with_suffix('.zip.sha256').read_text().split()[0]:
        raise RuntimeError('Full ZIP checksum mismatch')
    launcher=directory/'LowcaEcha-Launcher-Windows-x64.zip'
    if digest(launcher) != launcher.with_suffix('.zip.sha256').read_text().split()[0]:
        raise RuntimeError('Launcher ZIP checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='echo-release-') as temporary:
        notes=Path(temporary)/'notes.md'
        notes.write_text(f'Łowca Echa — Windows x64. Źródła: `{revision}`.\n\n'
                         'Rozpakuj launcher raz i uruchamiaj `Graj.exe`; kolejne aktualizacje pobiera sam. '
                         'Zapisy i ustawienia pozostają w `profile/`.\n',encoding='utf-8')
        tag=release['release_tag']
        existing=gh('release','view',tag,'--json','assets',capture=True,check=False)
        if existing.returncode:
            gh('release','create',tag,*map(str,bundles),'--target',revision,'--title','Windows '+revision[:12],
               '--notes-file',str(notes),'--latest=false')
        else:
            assets={asset['name']:asset for asset in json.loads(existing.stdout)['assets']}
            for path in bundles:
                if path.name in assets:
                    if assets[path.name]['size'] != path.stat().st_size:
                        raise RuntimeError('An immutable release asset has an unexpected size')
                else:
                    gh('release','upload',tag,str(path))
        # Recheck before advancing the mutable channel; old jobs cannot downgrade it.
        if gh('api',f'repos/{REPOSITORY}/commits/main','--jq','.sha',capture=True).stdout.strip() != revision:
            print('A newer build superseded this release; channel unchanged.')
            return
        channel='windows-latest'
        if gh('release','view',channel,capture=True,check=False).returncode:
            gh('release','create',channel,'--target',revision,'--title','Łowca Echa — Windows',
               '--notes-file',str(notes),'--latest')
        gh('release','upload',channel,str(directory/'update.json'),str(archive),str(archive.with_suffix('.zip.sha256')),
           str(launcher),str(launcher.with_suffix('.zip.sha256')),'--clobber')
        gh('release','edit',channel,'--title','Łowca Echa — Windows','--notes-file',str(notes),'--latest')


if __name__=='__main__':
    main()
