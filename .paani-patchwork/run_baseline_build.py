#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Waits for the source tree merge to finish and then runs the build.

The merge and the build are chained here so that the tree is never touched by
two processes at the same time.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('E:/eric/PaaniBrowserChromiumFork')
SRC = ROOT / 'paani-windows' / 'build' / 'src'
LOGS = ROOT / 'paani-windows' / 'logs'
MERGER_PID = int(sys.argv[1])


def process_alive(pid):
    try:
        import psutil  # noqa
    except ImportError:
        psutil = None
    if psutil is not None:
        return psutil.pid_exists(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def main():
    while process_alive(MERGER_PID):
        time.sleep(5)
    print('merger finished', flush=True)
    leftover = SRC / 'chromium-156.0.8078.79'
    print('leftover entries: %d' % (len(os.listdir(leftover)) if leftover.is_dir() else 0),
          flush=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log = LOGS / 'build-baseline.log'
    cmd = [sys.executable, str(ROOT / 'paani-windows' / 'build.py'),
           '--baseline', '--profile', 'personal', '-j', '6']
    print('running: %s' % ' '.join(cmd), flush=True)
    with open(log, 'w', encoding='utf-8', errors='replace') as handle:
        handle.write('$ %s\n\n' % ' '.join(cmd))
        handle.flush()
        result = subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT,
                                cwd=str(Path.home() / 'Documents' / 'Qoder' / '2026-10-31' / '12cf5842'))
    print('build exited with %s' % result.returncode, flush=True)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
