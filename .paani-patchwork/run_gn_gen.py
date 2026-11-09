#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Applies a patch series to the tree and runs gn gen.

Usage: run_gn_gen.py [series-dir]
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(r'E:\eric\PaaniBrowserChromiumFork')
PAANI = ROOT / 'paani-windows'
TREE = PAANI / 'build' / 'src'
PATCH_BIN = TREE / 'third_party/git/usr/bin/patch.exe'


def sdk_version():
    kits = (Path(os.environ.get('ProgramFiles(x86)',
                                 r'C:\Program Files (x86)')) /
            'Windows Kits' / '10' / 'Include')
    versions = []
    for entry in kits.iterdir():
        parts = entry.name.split('.')
        if len(parts) != 4 or not all(p.isdigit() for p in parts):
            continue
        if not (entry / 'um' / 'dwmapi.h').exists():
            continue
        versions.append(tuple(int(p) for p in parts))
    return '.'.join(str(p) for p in max(versions))


def vs_path():
    vswhere = '%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe'
    result = subprocess.run(
        '"{}" -products * -prerelease -latest -property installationPath'.format(vswhere),
        shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
    return result.stdout.strip()


def main():
    series = Path(sys.argv[1]) if len(sys.argv) > 1 else PAANI / 'patches/toolchain'

    sys.path.insert(0, str(PAANI / 'utils'))
    sys.path.insert(0, str(PAANI / 'helium-chromium' / 'utils'))
    import paani_patches
    applied = paani_patches.apply_series(series, TREE, PATCH_BIN)
    print('applied %d patches from %s' % (applied, series))

    env = dict(os.environ)
    env['PAANI_WINDOWS_SDK_VERSION'] = sdk_version()
    env['vs2022_install'] = vs_path()
    env['GYP_MSVS_OVERRIDE_PATH'] = vs_path()
    env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
    print('SDK %s, VS %s' % (env['PAANI_WINDOWS_SDK_VERSION'],
                             env['GYP_MSVS_OVERRIDE_PATH']))

    cmd = [str(TREE / 'buildtools/win/gn.exe'), 'gen', 'out\\Default',
           '--fail-on-unused-args']
    print('running:', ' '.join(cmd))
    result = subprocess.run(cmd, cwd=str(TREE), env=env)
    print('gn gen exit code:', result.returncode)
    return result.returncode


if __name__ == '__main__':
    sys.exit(main())
