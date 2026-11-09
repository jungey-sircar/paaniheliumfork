#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""Applies the pending edits to make_paani_patches.py.

The generator is stored with CRLF line endings, which makes multi line
string matching with the editor unreliable, so the edits are applied here.
"""

import ast
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / 'make_paani_patches.py'

text = TARGET.read_bytes().decode('utf-8')
had_crlf = '\r\n' in text
text = text.replace('\r\n', '\n')

EDITS = []

# ---------------------------------------------------------------------------
# The chrome/version.gni rule used a regular expression that never matched.
# The file is rewritten with three literal replacements instead.
# ---------------------------------------------------------------------------
EDITS.append((
    """    'chrome/version.gni': [
        Rule(r'helium_full = \\\\"@HELIUM_MAJOR@\\.@HELIUM_MINOR@"\\n(\\s+)"'
             r'\\.@HELIUM_PATCH@\\.@HELIUM_PLATFORM@\\\\"',
             r'paani_full = \\\\"@PAANI_MAJOR@.@PAANI_MINOR@"\\n\\g<1>"'
             r'.@PAANI_PATCH@.@PAANI_PLATFORM@\\\\"',
             regex=True),
        Rule('helium_version_full = _result.helium_full',
             'paani_version_full = _result.paani_full'),
    ],
""",
    """    'chrome/version.gni': [
        Rule(r'"helium_full = \\"@HELIUM_MAJOR@.@HELIUM_MINOR@"',
             r'"paani_full = \\"@PAANI_MAJOR@.@PAANI_MINOR@"'),
        Rule(r'".@HELIUM_PATCH@.@HELIUM_PLATFORM@\\" "',
             r'".@PAANI_PATCH@.@PAANI_PLATFORM@\\" "'),
        Rule('helium_version_full = _result.helium_full',
             'paani_version_full = _result.paani_full'),
    ],
"""))

# ---------------------------------------------------------------------------
# kHeliumSetupURL is not used by the onboarding page.
# ---------------------------------------------------------------------------
EDITS.append((
    """    'chrome/browser/ui/webui/onboarding/onboarding_page_ui.cc': [
        Rule('chrome::kHeliumSetupHost', 'chrome::kPaaniSetupHost'),
        Rule('chrome::kHeliumSetupURL', 'chrome::kPaaniSetupURL'),
    ],
""",
    """    'chrome/browser/ui/webui/onboarding/onboarding_page_ui.cc': [
        Rule('chrome::kHeliumSetupHost', 'chrome::kPaaniSetupHost'),
    ],
"""))

# ---------------------------------------------------------------------------
# New files need a /dev/null marker, otherwise patch cannot create them.
# ---------------------------------------------------------------------------
EDITS.append((
    """    proc = subprocess.run(
        ['diff', '-u', '--label', 'a/' + path, '--label', 'b/' + path,
         str(before_path), str(after_path)],
        capture_output=True, text=True, errors='replace')
    if proc.returncode not in (0, 1):
        FAILURES.append('diff failed for %s: %s' % (path, proc.stderr))
        return None
    return '--- a/%s\\n+++ b/%s\\n%s' % (path, path, proc.stdout)
""",
    """    old_label = '/dev/null' if not before else 'a/' + path
    proc = subprocess.run(
        ['diff', '-u', '--label', old_label, '--label', 'b/' + path,
         str(before_path), str(after_path)],
        capture_output=True, text=True, errors='replace')
    if proc.returncode not in (0, 1):
        FAILURES.append('diff failed for %s: %s' % (path, proc.stderr))
        return None
    return '--- %s\\n+++ b/%s\\n%s' % (old_label, path, proc.stdout)
"""))

# ---------------------------------------------------------------------------
# The Windows toolchain patch series.
# ---------------------------------------------------------------------------
EDITS.append((
    """PATCH_FILES = [
""",
    '''# ---------------------------------------------------------------------------
# Patch 5: the Windows toolchain
#
# Chromium 156 refuses to build with a Windows SDK that is older than
# 10.0.28000.0.  The SDK version becomes overridable, so that the browser can
# also be built on a machine that only has an older SDK installed, and the
# NTDDI level is lowered to the newest level that the oldest supported SDK
# still defines.
# ---------------------------------------------------------------------------
TOOLCHAIN = {
    'build/vs_toolchain.py': [
        Rule("SDK_VERSION = '10.0.28000.0'",
             "SDK_VERSION = os.environ.get('PAANI_WINDOWS_SDK_VERSION',\\n"
             "                          '10.0.28000.0')"),
    ],
    'build/toolchain/win/setup_toolchain.py': [
        Rule("SDK_VERSION = '10.0.28000.0'",
             "SDK_VERSION = os.environ.get('PAANI_WINDOWS_SDK_VERSION',\\n"
             "                          '10.0.28000.0')"),
    ],
    'build/config/win/BUILD.gn': [
        Rule('"NTDDI_VERSION=NTDDI_WIN11_BR"',
             '"NTDDI_VERSION=NTDDI_WIN10_NI"'),
    ],
    'base/win/windows_version.cc': [
        Rule('#if !defined(NTDDI_WIN11_BR)\\n'
             '#error Windows 10.0.28000.0 SDK or higher required.\\n'
             '#endif',
             '#if !defined(NTDDI_WIN10_NI)\\n'
             '#error Windows 10.0.22000.0 SDK or higher required.\\n'
             '#endif'),
    ],
}


TOOLCHAIN_FILES = [
    ('windows/paani-windows-sdk.patch',
     'Allows the browser to be built with a Windows SDK that is older than\\n'
     'the one that Chromium asks for.\\n',
     TOOLCHAIN),
]


PATCH_FILES = [
'''))

# ---------------------------------------------------------------------------
# The series files have to be written next to the patches.
# ---------------------------------------------------------------------------
EDITS.append((
    """def main():
    for entry in PATCH_FILES:
        rel_path, header, rules = entry[0], entry[1], entry[2]
        new_files = entry[3] if len(entry) > 3 else None
        body = build_patch(rel_path, rules, new_files)
        if body is None:
            FAILURES.append('patch %s is empty' % rel_path)
            continue
        dest = OUT / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(header + body, encoding='utf-8', newline='')
        print('wrote %s' % dest)

    if FAILURES:
""",
    """def emit(entries, out_dir):
    \"\"\"Writes the patches of one series and the series file next to them.\"\"\"
    out_dir = Path(out_dir)
    names = []
    for entry in entries:
        rel_path, header, rules = entry[0], entry[1], entry[2]
        new_files = entry[3] if len(entry) > 3 else None
        body = build_patch(rel_path, rules, new_files)
        if body is None:
            FAILURES.append('patch %s is empty' % rel_path)
            continue
        dest = out_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(header + body, encoding='utf-8', newline='')
        print('wrote %s' % dest)
        names.append(rel_path)
    series = out_dir / 'series'
    series.parent.mkdir(parents=True, exist_ok=True)
    series.write_text('\\n'.join(names) + '\\n', encoding='utf-8', newline='\\n')
    print('wrote %s' % series)


def main():
    emit(PATCH_FILES, OUT)
    emit(TOOLCHAIN_FILES, Path(OUT).parent / 'toolchain')

    if FAILURES:
"""))

applied = 0
for old, new in EDITS:
    count = text.count(old)
    if count != 1:
        print('ERROR: pattern found %d times:\n%s' % (count, old[:200]))
        sys.exit(1)
    text = text.replace(old, new)
    applied += 1

ast.parse(text)
TARGET.write_bytes(text.encode('utf-8'))
print('generator patched (%d replacements, crlf=%s)' % (applied, had_crlf))
