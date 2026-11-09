#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Applies the pending edits to the Paani build script.

build.py is stored with CRLF line endings, which makes multi line string
matching with the editor unreliable, so the edits are applied here.
"""

import ast
import sys
from pathlib import Path

TARGET = Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build.py')

text = TARGET.read_bytes().decode('utf-8')
had_crlf = '\r\n' in text
text = text.replace('\r\n', '\n')

EDITS = []

# ---------------------------------------------------------------------------
# The Windows SDK detection.
# ---------------------------------------------------------------------------
EDITS.append((
    """def _run_build_process(*args, **kwargs):
""",
    '''def _get_windows_sdk_version():
    """
    Returns the newest Windows SDK version that is installed.

    Chromium 156 asks for the Windows SDK 10.0.28000.0, which is not
    available on every machine.  The toolchain patch series makes the version
    overridable, and this function reports the version that is installed here.
    """
    kits = (Path(os.environ.get('ProgramFiles(x86)',
                                 r'C:\\Program Files (x86)')) /
            'Windows Kits' / '10' / 'Include')
    versions = []
    if kits.is_dir():
        for entry in kits.iterdir():
            if not entry.is_dir():
                continue
            parts = entry.name.split('.')
            if len(parts) != 4 or not all(part.isdigit() for part in parts):
                continue
            if not (entry / 'um' / 'dwmapi.h').exists():
                continue
            versions.append(tuple(int(part) for part in parts))
    if not versions:
        raise RuntimeError(
            'No Windows SDK with a usable um directory was found in %s' % kits)
    return '.'.join(str(part) for part in max(versions))


def _run_build_process(*args, **kwargs):
'''))

# ---------------------------------------------------------------------------
# The SDK version has to be part of the environment of the build.
# ---------------------------------------------------------------------------
EDITS.append((
    """    cmd_input.append('set "GYP_MSVS_OVERRIDE_PATH=%s"' % _get_visual_studio_path())
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\\n')
    subprocess.run(('cmd.exe', '/k'),
""",
    """    cmd_input.append('set "GYP_MSVS_OVERRIDE_PATH=%s"' % _get_visual_studio_path())
    cmd_input.append('set "PAANI_WINDOWS_SDK_VERSION=%s"' %
                     _get_windows_sdk_version())
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\\n')
    subprocess.run(('cmd.exe', '/k'),
"""))

EDITS.append((
    """    cmd_input.append('set "GYP_MSVS_OVERRIDE_PATH=%s"' % _get_visual_studio_path())
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\\n')
    with subprocess.Popen(('cmd.exe', '/k'), encoding=ENCODING, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) as proc:
""",
    """    cmd_input.append('set "GYP_MSVS_OVERRIDE_PATH=%s"' % _get_visual_studio_path())
    cmd_input.append('set "PAANI_WINDOWS_SDK_VERSION=%s"' %
                     _get_windows_sdk_version())
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\\n')
    with subprocess.Popen(('cmd.exe', '/k'), encoding=ENCODING, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) as proc:
"""))

# ---------------------------------------------------------------------------
# The toolchain patch series.
# ---------------------------------------------------------------------------
EDITS.append((
    """def _apply_paani_patches(source_tree):
""",
    '''def _apply_toolchain_patches(source_tree):
    """Applies the Paani Windows toolchain patches.

    They make the Windows SDK version overridable, so that the browser can
    also be built on a machine that has an older SDK installed.  They are
    applied to the baseline tree as well, because the baseline has to be built
    with exactly the same toolchain as the Paani tree.
    """
    paani_patches.apply_series(
        _ROOT_DIR / 'patches' / 'toolchain',
        source_tree,
        source_tree / _PATCH_BIN_RELPATH
    )


def _apply_paani_patches(source_tree):
'''))

EDITS.append((
    """                paani_patches.apply_series(
                    _ROOT_DIR / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                _mark_done('patched-helium')
""",
    """                paani_patches.apply_series(
                    _ROOT_DIR / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                _mark_done('patched-helium')

            # The toolchain patches have to come after the Helium series,
            # because the remote build patch touches the same file.
            if not _is_done('patched-toolchain'):
                _apply_toolchain_patches(source_tree)
                _mark_done('patched-toolchain')
"""))

applied = 0
for old, new in EDITS:
    count = text.count(old)
    if count != 1:
        print('ERROR: pattern found %d times:\\n%s' % (count, old[:200]))
        sys.exit(1)
    text = text.replace(old, new)
    applied += 1

ast.parse(text)
if had_crlf:
    text = text.replace('\n', '\r\n')
TARGET.write_bytes(text.encode('utf-8'))
print('build.py patched (%d replacements, crlf=%s)' % (applied, had_crlf))
