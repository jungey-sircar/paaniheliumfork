"""Finds tree files that still use the Helium identifiers Paani renamed away.

A rename patch that misses a call site does not fail until that translation
unit compiles, and one miss costs a full round trip through the build.  This
reads the identifiers removed by patches/paani/windows/*.patch, looks up every
file the upstream patches add a use of them in, and greps those files in
build/src.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAANI_PATCHES = ROOT / 'patches' / 'paani' / 'windows'
CORE_PATCHES = ROOT / 'helium-chromium' / 'patches'
SOURCE = ROOT / 'build' / 'src'

SYMBOL_RE = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*Helium[A-Za-z0-9_]*\b')
FILE_RE = re.compile(r'^\+\+\+ b/(\S+)')


def renamed_symbols():
    """Identifiers the Paani series deletes, so any use left behind is stale."""
    found = set()
    for patch in sorted(PAANI_PATCHES.glob('*.patch')):
        for line in patch.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.startswith('-') and not line.startswith('---'):
                found.update(SYMBOL_RE.findall(line))
    return sorted(found)


def users_of(symbol):
    """Tree files whose upstream patch hunks add a use of `symbol`."""
    users = set()
    for patch in sorted(CORE_PATCHES.rglob('*.patch')):
        current = None
        for line in patch.read_text(encoding='utf-8', errors='replace').splitlines():
            match = FILE_RE.match(line)
            if match:
                current = match.group(1)
            elif current and line.startswith('+') and symbol in line:
                users.add(current)
    return users


def main():
    symbols = renamed_symbols()
    print('renamed identifiers: %s' % ', '.join(symbols))
    stale = 0
    checked = set()
    for symbol in symbols:
        for relative in sorted(users_of(symbol)):
            path = SOURCE / relative
            if not path.is_file():
                print('MISSING from tree: %s (%s)' % (relative, symbol))
                continue
            if relative in checked:
                continue
            checked.add(relative)
            text = path.read_text(encoding='utf-8', errors='replace')
            hits = [i + 1 for i, line in enumerate(text.splitlines())
                    if any(s in line for s in symbols)]
            if hits:
                stale += 1
                print('STALE %s:%s' % (relative, ','.join(map(str, hits))))
    print('%d of %d candidate files still reference a renamed identifier'
          % (stale, len(checked)))

    staging = ROOT / 'src'
    for path in staging.rglob('*'):
        if not path.is_file() or path.suffix not in {'.cc', '.h', '.mm', '.gn', '.gni'}:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        hits = [i + 1 for i, line in enumerate(text.splitlines())
                if any(s in line for s in symbols)]
        if hits:
            print('STALE (staging) %s:%s' % (path.relative_to(staging),
                                             ','.join(map(str, hits))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
