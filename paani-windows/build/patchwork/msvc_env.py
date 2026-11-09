"""Captures the MSVC/vcvars64 environment once and caches it as JSON.

The Chromium build needs the Visual Studio toolchain environment.  The
existing build.py drives everything through `cmd.exe /k`, which makes it
impossible to capture output into a file.  This module extracts the
environment once so that plain subprocess calls can use it directly.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'build' / 'logs' / 'msvc_env.json'


def _capture():
    vcvars = ROOT / 'build' / 'msvc_env_probe.cmd'
    vcvars.parent.mkdir(parents=True, exist_ok=True)
    vcvars.write_text(
        '@echo off\r\n'
        'call "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022\\BuildTools'
        '\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\r\n'
        'set\r\n',
        encoding='utf-8')
    result = subprocess.run(['cmd.exe', '/c', str(vcvars)], capture_output=True,
                            text=True, errors='replace')
    env = {}
    for line in result.stdout.splitlines():
        if '=' not in line:
            continue
        key, _, value = line.partition('=')
        if key.startswith('='):
            continue
        env[key.strip()] = value.strip()
    return env


def environment():
    """Returns the build environment, using the cached copy when possible."""
    if CACHE.exists():
        try:
            env = json.loads(CACHE.read_text(encoding='utf-8'))
            if env:
                return env
        except (ValueError, OSError):
            pass
    env = _capture()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(env, indent=1), encoding='utf-8')
    return env


def build_environment():
    """The cached environment plus the Paani build tweaks from build.py."""
    env = dict(os.environ)
    env.update(environment())
    pybin = ROOT / 'build' / 'pybin'
    python_dir = Path(sys.executable).resolve().parent
    env['PATH'] = '%s;%s;%s' % (pybin, python_dir, env.get('PATH', ''))
    env['DEPOT_TOOLS_WIN_TOOLCHAIN'] = '0'
    env['GYP_MSVS_OVERRIDE_PATH'] = (
        r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools')
    env['vs2022_install'] = (
        r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools')
    return env
