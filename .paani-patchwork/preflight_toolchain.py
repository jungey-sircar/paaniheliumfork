#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compiles only the targets that the previous baseline run died on.

A full Chromium build costs a day, so the toolchain is validated against the
three objects that actually failed first: the ATL one and the two crypto
sources that need the wincrypt symbol prefix and the newer WinRT enum.  Extra
out/Default targets can be named on the command line instead.
"""

import os
import sys
from pathlib import Path

ROOT = Path('E:/eric/PaaniBrowserChromiumFork/paani-windows')
SRC = ROOT / 'build' / 'src'

sys.path.insert(0, str(ROOT))
import build  # noqa: E402  (reuses the upstream environment setup)

TARGETS = (
    'obj/base/base/atl_throw.obj',
    'obj/crypto/crypto/unexportable_key_win.obj',
    'obj/crypto/crypto/user_verifying_key_win.obj',
)


def main():
    version = build._check_windows_sdk(SRC)
    print('Windows SDK %s found' % version, flush=True)
    targets = tuple(sys.argv[1:]) or TARGETS
    os.chdir(SRC)
    # depot_tools otherwise picks its own siso and looks for a .sisoenv that
    # only a gclient checkout has.
    os.environ.setdefault('SISO_PATH',
                          str(SRC / 'third_party/siso/cipd/siso.exe'))
    if not (SRC / 'out' / 'Default' / 'build.ninja').exists():
        build._run_build_process('buildtools\\win\\gn.exe', 'gen',
                                 'out\\Default', '--fail-on-unused-args')
    build._run_build_process(sys.executable,
                             'third_party\\depot_tools\\autoninja.py',
                             '-j', '6', '-C', 'out\\Default', *targets)
    for target in targets:
        path = SRC / 'out' / 'Default' / Path(target).as_posix()
        print('%-6s %s' % ('ok' if path.exists() else 'MISSING', target),
              flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
