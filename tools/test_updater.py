#!/usr/bin/env python3
"""Compile and run update transaction tests on Windows or Mono."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
from package_windows import ROOT, compile_csharp

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--csharp-compiler')
parser.add_argument('--mono',help='Mono executable, required on Linux')
parser.add_argument('--feed-dir',type=Path,help='Reconstruct the actual published bundles instead of running fixture tests')
args=parser.parse_args()
output=ROOT/'build/updater-tests.exe'
output.parent.mkdir(exist_ok=True)
compile_csharp(output,[ROOT/'packaging/windows/UpdateCore.cs',ROOT/'tests/UpdaterTests.cs'],args.csharp_compiler,window=False)
runtime=[] if sys.platform=='win32' else [args.mono or shutil.which('mono') or 'mono']
subprocess.run(runtime+[str(output)]+(['--feed-dir',str(args.feed_dir.resolve())] if args.feed_dir else []),check=True)
