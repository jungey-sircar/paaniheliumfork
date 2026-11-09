#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moves whole directories up one level with a retry on a locked file.

A top level rename is a single metadata operation, so it is far cheaper than
the recursive merge that move_up.py performs.  It only works when the
destination does not exist yet.
"""

import os
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


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    names = sorted(os.listdir(src))
    for name in names:
        source = src / name
        destination = dst / name
        if destination.exists() or destination.is_symlink():
            print('skip (exists): %s' % name, flush=True)
            continue
        retry(lambda: os.rename(source, destination), 'moving %s' % name)
        print('moved: %s' % name, flush=True)
    left = sorted(os.listdir(src))
    if left:
        print('left over: %s' % ', '.join(left))
    return 0


if __name__ == '__main__':
    sys.exit(main())
