#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Removes the Paani Windows toolchain patch from the tree and from the series.

The patch made the Windows SDK version overridable so that Chromium could be
built against the 10.0.22621 SDK.  That is the wrong fix: Chromium 156 calls
APIs that simply do not exist in that SDK, so the correct move is to install
the SDK that upstream pins (10.0.28000.0) and leave build/ and base/ untouched.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path('E:/eric/PaaniBrowserChromiumFork/paani-windows')
SRC = ROOT / 'build' / 'src'
TOOLCHAIN = ROOT / 'patches' / 'toolchain'
PATCH = TOOLCHAIN / 'windows' / 'paani-windows-sdk.patch'
PATCH_BIN = SRC / 'third_party/git/usr/bin/patch.exe'

COMMON = ('-p1', '--ignore-whitespace', '--no-backup-if-mismatch',
          '--remove-empty-files')


def run(*extra):
    cmd = [str(PATCH_BIN), *COMMON, '-i', str(PATCH), '-d', str(SRC), *extra]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True)
    return result.returncode, result.stdout or ''


def main():
    if not PATCH.exists():
        print('patch file already removed')
    elif run('--dry-run', '--reverse')[0] != 0:
        print('the patch is not applied to the tree; nothing to revert')
    else:
        code, output = run('--reverse')
        if code != 0:
            print('reverse apply FAILED (%d):\n%s' % (code, output))
            return 1
        print('reverted the toolchain patch in the tree')

    if PATCH.exists():
        (TOOLCHAIN / 'windows').mkdir(parents=True, exist_ok=True)
        backup = PATCH.with_suffix('.patch.retired')
        PATCH.rename(backup)
        print('kept the retired patch for the record at %s' % backup.name)

    # An empty series keeps _apply_toolchain_patches() a no-op instead of
    # making build.py fail on a missing file.
    (TOOLCHAIN / 'series').write_text(
        '# Paani carries no toolchain patches: the machine has to provide the\n'
        '# Windows SDK that upstream Chromium pins (see README.md).\n',
        encoding='utf-8')

    checks = {
        SRC / 'build/vs_toolchain.py': "SDK_VERSION = '10.0.28000.0'",
        SRC / 'build/toolchain/win/setup_toolchain.py': "SDK_VERSION = '10.0.28000.0'",
        SRC / 'build/config/win/BUILD.gn': 'NTDDI_VERSION=NTDDI_WIN11_BR',
        SRC / 'base/win/windows_version.cc':
            '#error Windows 10.0.28000.0 SDK or higher required.',
    }
    failed = 0
    for path, expected in checks.items():
        text = path.read_text(encoding='utf-8', errors='replace')
        ok = expected in text
        print('%-5s %s' % ('ok' if ok else 'FAIL', path.relative_to(SRC)))
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
