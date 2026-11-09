"""Checks that every quoted #include in the Paani-owned staging sources resolves.

A missing header costs a full compile round trip, and the Paani files reference
plenty of Chromium internals that get renamed between releases. This walks only
the small set of Paani sources, so it runs in well under a second.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGING = ROOT / 'src'
TREE = ROOT / 'build' / 'src'

INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"')


def main():
    missing = []
    checked = 0
    for path in sorted(STAGING.rglob('*')):
        if path.suffix not in ('.cc', '.h', '.hpp', '.mmm') or not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for line in text.splitlines():
            match = INCLUDE_RE.match(line)
            if not match:
                continue
            header = match.group(1)
            checked += 1
            if header.startswith('paani/') or 'chrome/browser/paani' in header:
                continue
            if not (TREE / header).exists():
                missing.append((str(path.relative_to(STAGING)), header))
    print('checked includes: %d' % checked)
    for source, header in missing:
        print('MISSING  %s -> %s' % (source, header))
    print('missing: %d' % len(missing))
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main())
