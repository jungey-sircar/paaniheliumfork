"""Apply the Helium patch series to a scratch subset of the Chromium tree.

The subset only contains the files the Paani patches touch, so most patches
report "can't find file to patch" for everything else.  Those are expected and
ignored; what matters is that no hunk that *does* touch one of our files
fails.
"""
import subprocess
import pathlib
import sys

root = pathlib.Path('E:/eric/PaaniBrowserChromiumFork')
work = pathlib.Path(sys.argv[1]).resolve()
tracked = {p.relative_to(work).as_posix()
           for p in work.rglob('*') if p.is_file()}

series_files = [
    root / 'paani-windows' / 'helium-chromium' / 'patches' / 'series',
    root / 'paani-windows' / 'patches' / 'series',
]

problems = []
for sf in series_files:
    base_dir = sf.parent
    for line in sf.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = base_dir / line
        if not p.exists():
            problems.append('MISSING PATCH FILE ' + str(p))
            continue
        proc = subprocess.run(
            ['patch', '-p1', '--batch', '--forward', '-i', str(p)],
            cwd=str(work), capture_output=True, text=True, errors='replace')
        out = proc.stdout + proc.stderr
        current = None
        for raw in out.splitlines():
            txt = raw.strip()
            if txt.startswith('patching file '):
                current = txt[len('patching file '):].strip()
            if 'FAILED' in txt and current in tracked:
                problems.append('%s: %s: %s' % (line, current, txt))
        if 'Reversed (or previously applied) patch detected' in out:
            problems.append(line + ': reversed/previous patch')

print('tracked files:', len(tracked))
print('problems:', len(problems))
for x in problems:
    print('  ', x)
