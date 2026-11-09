#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Applies the Paani patch series to a copy of the files it touches.

The build tree cannot be used for this, because the build is reading from it
and because a failed apply would leave the tree in a mixed state.  Only the
files that the series touches are copied, which is enough for `patch` to work
on them.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TREE = Path(sys.argv[1]).resolve()
SERIES_DIR = Path(sys.argv[2]).resolve()

HEADER = re.compile(r'^--- (?:a/)?(\S+)\n\+\+\+ (?:b/)?(\S+)$', re.M)


def touched_files(patch_text):
    """Returns every path that the patch adds, changes or removes."""
    paths = set()
    for old, new in HEADER.findall(patch_text):
        for path in (old, new):
            if path == '/dev/null':
                continue
            paths.add(path)
    return paths


def created_files(patch_text):
    """Returns the paths that the patch creates out of nothing."""
    return {new for old, new in HEADER.findall(patch_text)
            if old == '/dev/null'}


def main():
    series = [line.strip() for line in
              Path(SERIES_DIR, 'series').read_text(encoding='utf-8').splitlines()
              if line.strip() and not line.startswith('#')]

    scratch = Path(tempfile.mkdtemp(prefix='paani-verify-'))
    print('scratch: %s' % scratch)

    failures = 0
    known = set()
    for number, name in enumerate(series, start=1):
        patch_path = Path(SERIES_DIR, name)
        patch_text = patch_path.read_text(encoding='utf-8')

        missing = []
        for path in sorted(touched_files(patch_text) - created_files(
                patch_text)):
            if path in known:
                continue
            src = TREE / path
            if not src.exists():
                missing.append(path)
                continue
            dest = scratch / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        if missing:
            failures += 1
            print('FAIL %s, missing in the tree:' % name)
            for path in missing:
                print('  ' + path)
            continue

        cmd = ['patch', '-p1', '--ignore-whitespace', '--no-backup-if-mismatch',
               '--remove-empty-files', '--forward', '-i', str(patch_path),
               '-d', str(scratch)]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                errors='replace')
        if result.returncode != 0:
            failures += 1
            print('FAIL %s' % name)
            print(result.stdout or result.stderr)
        else:
            print('ok   %s' % name)

        known |= created_files(patch_text)

    shutil.rmtree(scratch, ignore_errors=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
