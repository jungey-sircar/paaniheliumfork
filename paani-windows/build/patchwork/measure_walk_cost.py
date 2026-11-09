"""Measure how many directory entries the substitution walk touches.

os.walk() in Helium's get_substitutable_files() enumerates every directory,
including out/ and .git/, which a built Chromium tree makes enormous.  This
counts entries per top-level subtree so the cost is visible.
"""

import os
import sys
import time
from pathlib import Path

SRC = Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src')
LIMIT = float(sys.argv[1]) if len(sys.argv) > 1 else 45.0


def count(path, deadline):
    dirs = files = 0
    for root, names, filenames in os.walk(path):
        dirs += len(names)
        files += len(filenames)
        if time.monotonic() > deadline:
            return dirs, files, 'TIMEOUT'
    return dirs, files, 'ok'


for name in sorted(p.name for p in SRC.iterdir() if p.is_dir()):
    if name not in ('.git', 'out', 'chrome', 'ui', 'components'):
        continue
    start = time.monotonic()
    d, f, status = count(SRC / name, start + LIMIT)
    print(f'{name:<12} dirs={d:<9} files={f:<10} {time.monotonic() - start:6.1f}s {status}',
          flush=True)
