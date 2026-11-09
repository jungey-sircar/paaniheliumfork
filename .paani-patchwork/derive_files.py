"""Derive the exact set of source files that the Paani patch series needs.

Both patch series are parsed for their "--- a/<path>" / "+++ b/<path>" headers.
The union of those paths is the subset of the Chromium tree that must be
extracted and patched to obtain a faithful post-Helium baseline.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path('E:/eric/PaaniBrowserChromiumFork')

SERIES = [
    ROOT / 'paani-windows' / 'helium-chromium' / 'patches' / 'series',
    ROOT / 'paani-windows' / 'patches' / 'series',
    ROOT / 'paani-windows' / 'patches' / 'paani' / 'series',
]

FILE_RE = re.compile(r'^diff --git a/(\S+) b/(\S+)$')
OLD_RE = re.compile(r'^--- (?:a/)?(\S+)')
NEW_RE = re.compile(r'^\+\+\+ (?:b/)?(\S+)')

files = set()
for series in SERIES:
    base = series.parent
    for line in series.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        patch = base / line
        if not patch.exists():
            print('MISSING PATCH', patch)
            continue
        text = patch.read_text(encoding='utf-8', errors='replace')
        for raw in text.splitlines():
            m = FILE_RE.match(raw)
            if m:
                files.add(m.group(2))
                continue
            m = OLD_RE.match(raw) or NEW_RE.match(raw)
            if m:
                p = m.group(1)
                if p not in ('/dev/null',):
                    files.add(p)

files = {f for f in files if not f.endswith('.orig') and not f.endswith('.rej')}
out = sorted(files)
dest = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path('/tmp/paani_files2.txt')
dest.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('files:', len(out))
print('wrote', dest)
for f in out:
    print(' ', f)
