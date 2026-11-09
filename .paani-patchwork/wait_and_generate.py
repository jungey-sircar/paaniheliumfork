#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Waits for the post-Helium source tree and then generates the Paani patches.

The build driver applies the Helium series, the domain and name substitution
and the i18n step to paani-windows/build/src in place.  The Paani patches have
to be generated from that exact state, so this script waits for the HELIUM_*
marker in chrome/VERSION, snapshots the files that the patch series and the
Paani rules touch, and runs the patch generator on the snapshot.
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('E:/eric/PaaniBrowserChromiumFork')
TREE = ROOT / 'paani-windows' / 'build' / 'src'
SNAPSHOT = ROOT / '.paani-patchwork' / 'base3'
FILE_LIST = ROOT / '.paani-patchwork' / 'paani_files.txt'
OUT = ROOT / 'paani-windows' / 'patches' / 'paani'
LOG = ROOT / 'logs' / 'generate-patches.log'
GENERATOR = ROOT / '.paani-patchwork' / 'make_paani_patches.py'
DERIVER = ROOT / '.paani-patchwork' / 'derive_files.py'


def log(message):
    stamp = time.strftime('%H:%M:%S')
    line = '[%s] %s' % (stamp, message)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def tree_ready():
    version = TREE / 'chrome' / 'VERSION'
    if not version.exists():
        return False
    return 'HELIUM_MAJOR' in version.read_text(encoding='utf-8', errors='replace')


def wait_for_tree(timeout=21600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tree_ready():
            return True
        time.sleep(20)
    return False


def build_file_list():
    """Returns the union of the patched files and the files the rules touch."""
    paths = set()
    proc = subprocess.run([sys.executable, str(DERIVER), str(FILE_LIST)],
                          capture_output=True, text=True, errors='replace')
    if proc.returncode != 0:
        log('derive_files.py failed:\n%s' % proc.stderr)
    if FILE_LIST.exists():
        for raw in FILE_LIST.read_text(encoding='utf-8').splitlines():
            if raw.strip():
                paths.add(raw.strip())
    # The rules may touch files that no upstream patch touches.
    proc = subprocess.run(
        [sys.executable, '-c',
         'import importlib.util, sys; '
         'spec = importlib.util.spec_from_file_location("gen", %r); '
         'mod = importlib.util.module_from_spec(spec); '
         'spec.loader.exec_module(mod); '
         'print("\\n".join(mod.referenced_paths()))' % str(GENERATOR)],
        capture_output=True, text=True, errors='replace')
    if proc.returncode != 0:
        log('referenced_paths() failed:\n%s' % proc.stderr)
    else:
        paths.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(paths)


def snapshot(paths):
    """Copies the needed files out of the live tree."""
    if SNAPSHOT.exists():
        shutil.rmtree(SNAPSHOT, ignore_errors=True)
    copied = 0
    missing = []
    for rel in paths:
        src = TREE / rel
        dest = SNAPSHOT / rel
        if not src.exists():
            missing.append(rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    log('snapshot: copied %d files, %d missing' % (copied, len(missing)))
    for rel in missing[:40]:
        log('  missing: %s' % rel)
    return missing


def generate():
    proc = subprocess.run(
        [sys.executable, str(GENERATOR), str(SNAPSHOT), str(OUT)],
        capture_output=True, text=True, errors='replace')
    with open(LOG, 'a', encoding='utf-8') as handle:
        handle.write(proc.stdout)
        handle.write(proc.stderr)
    log('generator exit code %d' % proc.returncode)
    return proc.returncode


def main():
    if not tree_ready():
        log('waiting for the post-Helium tree at %s' % TREE)
        if not wait_for_tree():
            log('TIMEOUT waiting for the post-Helium tree')
            return 1
    log('post-Helium tree ready')
    paths = build_file_list()
    log('file list: %d files' % len(paths))
    snapshot(paths)
    return generate()


if __name__ == '__main__':
    sys.exit(main())
