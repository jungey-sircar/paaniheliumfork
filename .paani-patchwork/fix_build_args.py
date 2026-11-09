#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Rewrites the args.gn generation of the Paani build script.

The flags of the Helium tree and of the Windows tree overlap, and the same
flag was set twice again by the build profiles.  GN takes the last value, but
the duplicated assignments are confusing, so the flags are merged into one
dictionary and every flag is written exactly once.
"""

import ast
import sys
from pathlib import Path

TARGET = Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build.py')

text = TARGET.read_bytes().decode('utf-8')
had_crlf = '\r\n' in text
text = text.replace('\r\n', '\n')

EDITS = []

EDITS.append((
    """def _run_build_process(*args, **kwargs):
""",
    '''def _read_gn_flags(path):
    """
    Reads a GN flag file into a dictionary.

    A flag that is set in more than one file keeps the value of the last
    file, and a flag that is set twice in the same file keeps the value of
    the last line.
    """
    values = {}
    for line in path.read_text(encoding=ENCODING).splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            continue
        values[key.strip()] = value.strip()
    return values


def _run_build_process(*args, **kwargs):
'''))

EDITS.append((
    """        gn_flags = (_ROOT_DIR / 'helium-chromium' / 'flags.gn').read_text(encoding=ENCODING)
        gn_flags += '\\n'
        windows_flags = (_ROOT_DIR / 'flags.windows.gn').read_text(encoding=ENCODING)
        if args.arm:
            windows_flags = windows_flags.replace('x64', 'arm64')
        if args.dev:
            windows_flags += '\\nchrome_pgo_phase=0\\n'

        if os.environ.get('SISO_REAPI_ADDRESS'):
            windows_flags += 'use_remoteexec = true\\n'
            # Precompiled modules are not portable across Windows/Linux hosts.
            windows_flags += 'use_clang_modules = false\\n'
        elif shutil.which('sccache'):
            windows_flags += 'cc_wrapper = "sccache"\\n'

        gn_flags += windows_flags
        if args.dev:
            gn_flags += 'is_component_build=true\\n'
        else:
            gn_flags += 'is_official_build=true\\n'

        if args.profile == 'personal':
            # is_official_build turns on ThinLTO on Windows, and the resulting
            # link of chrome.dll needs far more RAM than a typical desktop has
            # to spare.  PGO phase 2 adds two more full builds plus a training
            # run on top of that.  Both are dropped here; the baseline and the
            # Paani build use the same profile, so the comparison stays fair.
            gn_flags += 'is_official_build=false\\n'
            gn_flags += 'chrome_pgo_phase=0\\n'

        winsparkle_ed_key = os.environ.get('WINSPARKLE_ED_KEY', '')
        authenticode_org = os.environ.get('WINSPARKLE_AUTHENTICODE_ORG', '')
        if winsparkle_ed_key and authenticode_org:
            gn_flags += 'enable_winsparkle=true\\n'
            gn_flags += f'winsparkle_ed_key="{winsparkle_ed_key}"\\n'
            gn_flags += f'winsparkle_authenticode_org="{authenticode_org}"\\n'

        (source_tree / 'out/Default/args.gn').write_text(gn_flags, encoding=ENCODING)
""",
    """        gn_values = _read_gn_flags(_ROOT_DIR / 'helium-chromium' / 'flags.gn')
        windows_values = _read_gn_flags(_ROOT_DIR / 'flags.windows.gn')
        if args.arm:
            windows_values = {key: value.replace('x64', 'arm64')
                              for key, value in windows_values.items()}
        gn_values.update(windows_values)

        if args.dev:
            gn_values['chrome_pgo_phase'] = '0'
            gn_values['is_component_build'] = 'true'
        else:
            gn_values['is_official_build'] = 'true'

        if args.profile == 'personal':
            # is_official_build turns on ThinLTO on Windows, and the resulting
            # link of chrome.dll needs far more RAM than a typical desktop has
            # to spare.  PGO phase 2 adds two more full builds plus a training
            # run on top of that.  Both are dropped here; the baseline and the
            # Paani build use the same profile, so the comparison stays fair.
            gn_values['is_official_build'] = 'false'
            gn_values['chrome_pgo_phase'] = '0'

        if os.environ.get('SISO_REAPI_ADDRESS'):
            gn_values['use_remoteexec'] = 'true'
            # Precompiled modules are not portable across Windows/Linux hosts.
            gn_values['use_clang_modules'] = 'false'
        elif shutil.which('sccache'):
            gn_values['cc_wrapper'] = '"sccache"'

        winsparkle_ed_key = os.environ.get('WINSPARKLE_ED_KEY', '')
        authenticode_org = os.environ.get('WINSPARKLE_AUTHENTICODE_ORG', '')
        if winsparkle_ed_key and authenticode_org:
            gn_values['enable_winsparkle'] = 'true'
            gn_values['winsparkle_ed_key'] = '\"%s\"' % winsparkle_ed_key
            gn_values['winsparkle_authenticode_org'] = '\"%s\"' % authenticode_org

        (source_tree / 'out/Default/args.gn').write_text(
            ''.join('%s=%s\\n' % (key, value)
                    for key, value in gn_values.items()),
            encoding=ENCODING)
"""))

applied = 0
for old, new in EDITS:
    count = text.count(old)
    if count != 1:
        print('ERROR: pattern found %d times:\n%s' % (count, old[:300]))
        sys.exit(1)
    text = text.replace(old, new)
    applied += 1

ast.parse(text)
if had_crlf:
    text = text.replace('\n', '\r\n')
TARGET.write_bytes(text.encode('utf-8'))
print('build.py patched (%d replacements, crlf=%s)' % (applied, had_crlf))
