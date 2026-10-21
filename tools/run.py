#!/usr/bin/env python3
"""Run the standalone game, or its engine tests on a private virtual display."""
import argparse
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

from setup import ENGINE, ROOT, RUNTIME, TEMPLATE, engine_binary, platform_key


def configure(profile, test):
    profile.mkdir(parents=True,exist_ok=True)
    user = profile/'user'
    user.mkdir(exist_ok=True)
    (user/'data').mkdir(exist_ok=True)
    lines = ['replace=config','replace=data','replace=content','replace=fallback-archive',
             f'user-data="{user.as_posix()}"', f'data-local="{(user / "data").as_posix()}"']
    for path in (TEMPLATE/'game_template/data', TEMPLATE/'example_animated_creature/data', ROOT/'build/data', ROOT/'game'):
        lines.append(f'data="{path.as_posix()}"')
    lines += ['content=template.omwgame','content=echo.omwaddon','content=echo.omwscripts',
              'start=Echo Arena','skip-menu=1','new-game=0']
    if test:
        lines += [f'data="{(ROOT / "tests/engine").as_posix()}"','content=echo-tests.omwscripts','no-sound=1']
    (profile/'openmw.cfg').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    settings=(ROOT/'config/settings.cfg').read_text(encoding='utf-8')
    if test:
        settings=settings.replace('vsync = true','vsync = false')
    if test or not (profile/'settings.cfg').exists():
        (profile/'settings.cfg').write_text(settings,encoding='utf-8')


def stop(process):
    if process is None or process.poll() is not None:
        return
    if os.name == 'nt':
        process.terminate()
    else:
        os.killpg(process.pid,signal.SIGTERM)
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            process.kill()
        else:
            os.killpg(process.pid,signal.SIGKILL)
        process.wait()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--test',action='store_true',help='Run engine integration tests and exit')
    parser.add_argument('--headless',action='store_true',help='Create a private software-rendered Xorg display')
    parser.add_argument('--load',type=Path,help='Load an existing .omwsave')
    parser.add_argument('--capture',type=Path,help='Capture the actual game frame to PNG, then stop')
    parser.add_argument('--timeout',type=int,default=90,help='Maximum duration of engine tests')
    args=parser.parse_args()
    windows = platform_key() == 'windows'
    if windows and (args.headless or args.capture):
        parser.error('--headless and --capture are Linux tools; on Windows use --test in a desktop session')
    if not engine_binary().exists():
        parser.error('Run python tools/setup.py first')
    subprocess.run([sys.executable,str(ROOT/'tools/build_content.py')],check=True)
    profile=RUNTIME/('test-profile' if args.test else 'profile')
    configure(profile,args.test)
    if args.headless and not args.test:
        with (profile/'openmw.cfg').open('a',encoding='utf-8') as config:
            config.write('no-sound=1\n')
    env=dict(os.environ)
    for key, directory in [('XDG_CONFIG_HOME','xdg-config'),('XDG_DATA_HOME','xdg-data'),
                           ('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','run'),('MESA_SHADER_CACHE_DIR','mesa-cache')]:
        path=profile/directory;path.mkdir(exist_ok=True,mode=0o700);env[key]=str(path)
    if not windows:
        env['LD_LIBRARY_PATH']=str(ENGINE/'lib')
    xserver=engine=None
    try:
        if not windows and (args.headless or not env.get('DISPLAY')):
            env['LIBGL_ALWAYS_SOFTWARE']='1'
            readfd,writefd=os.pipe()
            with (profile/'xorg-stdout.log').open('w') as log:
                xserver=subprocess.Popen(['Xorg','-displayfd',str(writefd),'-noreset','-nolisten','tcp',
                    '-config',str(ROOT/'config/xorg.conf'),'-logfile',str(profile/'xorg.log')],
                    pass_fds=(writefd,),stdout=log,stderr=log,start_new_session=True)
            os.close(writefd)
            ready,_,_=select.select([readfd],[],[],15)
            display=os.read(readfd,32).decode().strip() if ready else ''
            os.close(readfd)
            if not display:
                raise RuntimeError('Virtual display failed; see '+str(profile/'xorg-stdout.log'))
            env['DISPLAY']=':'+display
            print('Virtual display '+env['DISPLAY'],flush=True)
        config_argument = os.path.relpath(profile, ENGINE) if windows else str(profile)
        command=[str(engine_binary()),'--config',config_argument,'--no-grab']
        if args.load:
            command+=['--load-savegame',str(args.load.resolve())]
        log_path = profile/'openmw.log'
        previous_log = log_path.stat().st_mtime_ns if log_path.exists() else None
        def current_log():
            if not log_path.exists() or log_path.stat().st_mtime_ns == previous_log:
                return ''
            return log_path.read_text(encoding='utf-8',errors='replace')
        with (profile/'stdout.log').open('w') as log:
            options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if windows else {'start_new_session': True}
            engine=subprocess.Popen(command,cwd=ENGINE,env=env,stdout=log,stderr=subprocess.STDOUT,**options)
        print('OpenMW started. Logs: '+str(profile/'openmw.log'),flush=True)
        started=time.monotonic()
        ready_at = None
        while engine.poll() is None:
            if (args.test or args.capture) and time.monotonic()-started>args.timeout:
                raise TimeoutError('Engine tests did not finish before the timeout')
            if args.capture:
                logs = current_log()
                if 'EH_READY' in logs and ready_at is None:
                    ready_at = time.monotonic()
                if ready_at and time.monotonic()-ready_at > 1.0:
                    if ' E]' in logs:
                        raise RuntimeError('Engine reported an error; see '+str(profile/'openmw.log'))
                    destination = args.capture.resolve()
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    subprocess.run(['import','-display',env['DISPLAY'],'-window','root',str(destination)],check=True)
                    print('Captured actual OpenMW frame: '+str(destination))
                    return
            time.sleep(0.2)
        status=engine.returncode
        logs=current_log()
        if args.test:
            print('\n'.join(line for line in logs.splitlines() if 'EH_' in line or ' E]' in line))
            if status!=0 or 'EH_TESTS_PASSED' not in logs or ' E]' in logs:
                raise RuntimeError('Engine validation failed; see '+str(profile/'stdout.log'))
            print('Engine integration tests passed.')
        elif status!=0:
            raise RuntimeError('OpenMW exited with status '+str(status)+'; see '+str(profile/'stdout.log'))
    finally:
        stop(engine)
        stop(xserver)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
