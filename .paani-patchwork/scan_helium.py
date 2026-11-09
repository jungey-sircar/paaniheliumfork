#!/usr/bin/env python3
"""Lists the files that still contain a Helium identifier."""
import re
import sys
from pathlib import Path

TREE = Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src')
ROOTS = ['chrome', 'ui', 'components', 'content', 'build', 'third_party/blink',
         'base', 'net', 'services', 'extensions']

SKIP = re.compile(r'(third_party/blink/renderer/core/css|test/data|test/)'
                   r'|(\.png|\.ico|\.svg|\.webp|\.gif|\.ttf|\.woff)')

tokens = {}
for root in ROOTS:
    base = TREE / root
    if not base.is_dir():
        continue
    for path in base.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(TREE).as_posix()
        if SKIP.search(rel):
            continue
        if path.suffix not in ('.cc', '.h', '.mm', '.m', '.py', '.gn', '.gni',
                               '.ts', '.html', '.js', '.grd', '.grdp', '.json',
                               '.txt', '.md', '.csv', '.xml', '.yaml', '.yml',
                               '.rc', '.manifest', '.template', '.in', '.version'):
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        hits = re.findall(r'[Hh][Ee][Ll][Ii][Uu][Mm]\w*', text)
        if hits:
            uniq = sorted(set(hits))
            tokens[rel] = (len(hits), uniq)

for rel in sorted(tokens):
    count, uniq = tokens[rel]
    print('%-95s %4d  %s' % (rel, count, ', '.join(uniq[:12])))
print('\n%d files' % len(tokens))
