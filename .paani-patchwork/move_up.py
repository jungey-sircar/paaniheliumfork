#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moves the contents of the extracted Chromium tree up one level.

The upstream helper does the same move with Path.rename(), but it gives up on
the first directory that Windows happens to have locked, and Path.is_dir()
raises on the dangling symlinks that the source archive contains.  This script
moves the entries one by one, retries a locked entry and treats a symlink as
a file so that it is never followed.
"""

import os
import shutil
import stat
import sys
import time
from pathlib import Path

ATTEMPTS = 60
DELAY = 2.0
LOCK_ERRORS = (5, 32)


def is_locked(exc):
    return getattr(exc, 'winerror', None) in LOCK_ERRORS


def retry(action, description):
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return action()
        except OSError as exc:
            if attempt == ATTEMPTS or not is_locked(exc):
                raise
            print('  locked: %s (%s), retry %d' %
                  (description, exc.strerror, attempt), flush=True)
            time.sleep(DELAY)


def is_link(path):
    return stat.S_ISLNK(os.lstat(path).st_mode)


def is_dir(path):
    return stat.S_ISDIR(os.lstat(path).st_mode)


def remove_dir(path):
    """Removes an empty directory, tolerating a directory that is in use."""
    try:
        path.rmdir()
        return True
    except OSError as exc:
        print('  could not remove %s: %s' % (path, exc), flush=True)
        return False


def merge(source, destination):
    """Moves source onto destination, merging directories recursively."""
    if is_dir(source) and not is_link(source):
        if destination.is_dir() and not is_link(destination):
            for child in source.iterdir():
                merge(child, destination / child.name)
            remove_dir(source)
            return
        # The directory cannot be renamed as a whole, so its contents are
        # moved into the destination one by one.
        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            merge(child, destination / child.name)
        remove_dir(source)
        return
    if destination.is_symlink() or destination.is_file():
        retry(destination.unlink, 'unlink %s' % destination)
    elif destination.is_dir():
        shutil.rmtree(destination)
    retry(lambda: source.rename(destination), 'rename %s' % source)


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    if not src.is_dir():
        print('nothing to move: %s does not exist' % src)
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    names = sorted(os.listdir(src))
    print('moving %d entries from %s' % (len(names), src), flush=True)
    done = 0
    for name in names:
        merge(src / name, dst / name)
        done += 1
        if done % 25 == 0:
            print('  %d/%d' % (done, len(names)), flush=True)
    print('moved %d entries' % done, flush=True)
    left = sorted(os.listdir(src))
    if left:
        print('left over in %s: %s' % (src, ', '.join(left)))
    try:
        src.rmdir()
        print('removed %s' % src)
    except OSError as exc:
        print('could not remove %s: %s' % (src, exc))
    return 0


if __name__ == '__main__':
    sys.exit(main())
