"""Restore the pristine frame-view files behind the backdrop patch, then re-record.

The recorder refuses to re-apply its substitutions to a tree that already carries
them, so a corrected backdrop change has to start from the pristine copies in
build/patchwork/orig/backdrop/.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'backdrop'
STAGED = ROOT / 'src' / 'chrome/browser/ui/views/frame'

FILES = {
    'chrome/browser/ui/views/frame/browser_frame_view_win.h':
        'chrome_browser_ui_views_frame_browser_frame_view_win.h.orig',
    'chrome/browser/ui/views/frame/browser_frame_view_win.cc':
        'chrome_browser_ui_views_frame_browser_frame_view_win.cc.orig',
    'chrome/browser/ui/views/frame/BUILD.gn':
        'chrome_browser_ui_views_frame_BUILD.gn.orig',
}

for relative, backup_name in FILES.items():
    target = SOURCE / relative
    pristine = BACKUP / backup_name
    if not pristine.exists():
        raise SystemExit(f'missing pristine copy: {pristine}')
    shutil.copyfile(pristine, target)
    print(f'restored {relative}')

for name in ('paani_chrome_backdrop.h', 'paani_chrome_backdrop.cc'):
    shutil.copyfile(STAGED / name, SOURCE / 'chrome/browser/ui/views/frame' / name)
    print(f'staged {name}')

sys.exit(subprocess.call([sys.executable,
                          str(ROOT / 'build/patchwork/make_backdrop_patch.py')],
                         cwd=str(ROOT)))
