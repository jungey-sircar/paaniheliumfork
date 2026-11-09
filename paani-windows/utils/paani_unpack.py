#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2026 The Paani Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Makes the archive unpacking survive transient Windows file locks.

The upstream extraction helper moves the contents of an extracted archive one
level up with Path.rename().  On Windows that call fails with "Access is
denied" or "The process cannot access the file because it is being used by
another process" as soon as a background scanner holds a handle on one of the
freshly written directories, and the failure aborts a build that has already
spent half an hour on the download.  The helpers here retry the move and can
finish a move that was interrupted halfway through.
"""

import os
import shutil
import stat
import time
from pathlib import Path

from _common import get_logger

ATTEMPTS = 90
DELAY = 2.0
LOCK_ERRORS = (5, 32)


def _is_locked(exc):
    """Returns whether the error is a transient Windows file lock."""
    return getattr(exc, 'winerror', None) in LOCK_ERRORS


def _retry(action, description):
    """Runs action, retrying it while Windows reports a file lock."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return action()
        except OSError as exc:
            if attempt == ATTEMPTS or not _is_locked(exc):
                raise
            get_logger().warning('%s is locked (%s), retrying in %.0f seconds',
                                 description, exc.strerror, DELAY)
            time.sleep(DELAY)


def _is_link(path):
    """Returns whether the path is a symbolic link.

    The link is not followed, because the source archive contains links that
    point outside of the tree and stat()ing them fails.
    """
    return stat.S_ISLNK(os.lstat(path).st_mode)


def _is_dir(path):
    """Returns whether the path is a directory, without following a link."""
    return stat.S_ISDIR(os.lstat(path).st_mode)


def _remove_dir(path):
    """Removes an empty directory, tolerating a directory that is in use."""
    try:
        _retry(path.rmdir, 'removing %s' % path)
        return True
    except OSError as exc:
        get_logger().warning('Could not remove %s: %s', path, exc)
        return False


def _merge(source, destination):
    """Moves source onto destination, merging directories recursively."""
    if _is_dir(source) and not _is_link(source):
        if not os.path.lexists(destination):
            # Nothing is in the way, so the whole directory moves in one
            # operation instead of one file at a time.
            _retry(lambda: source.rename(destination), 'moving %s' % source)
            return
        if destination.is_dir() and not _is_link(destination):
            for child in source.iterdir():
                _merge(child, destination / child.name)
            _remove_dir(source)
            return
        # The directory cannot be renamed as a whole, so its contents are
        # moved into the destination one by one.
        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            _merge(child, destination / child.name)
        _remove_dir(source)
        return
    if destination.is_symlink() or destination.is_file():
        _retry(destination.unlink, 'removing %s' % destination)
    elif destination.is_dir():
        shutil.rmtree(destination)
    _retry(lambda: source.rename(destination), 'moving %s' % source)


def process_relative_to(unpack_root, relative_to):
    """Moves the contents of unpack_root/relative_to up into unpack_root.

    A relative_to of None means that the archive has no leading directory to
    strip, so there is nothing to move.
    """
    if relative_to is None:
        return
    relative_root = Path(unpack_root) / relative_to
    if not relative_root.is_dir():
        get_logger().error('Could not find relative_to directory in extracted files: %s',
                           relative_to)
        raise FileNotFoundError()
    # A locked directory is retried, and a pass that runs into a lock that
    # outlives the retries is retried as a whole: the entries that were
    # already moved stay moved.
    for attempt in range(1, ATTEMPTS + 1):
        try:
            for src_path in relative_root.iterdir():
                _merge(src_path, Path(unpack_root) / src_path.name)
            _remove_dir(relative_root)
            return
        except OSError as exc:
            if attempt == ATTEMPTS or not _is_locked(exc):
                raise
            get_logger().warning('%s is locked (%s), retrying the whole move',
                                 relative_root, exc.strerror)
            time.sleep(DELAY)


def install():
    """Makes the upstream extraction helper use the retrying move."""
    import _extraction
    _extraction._process_relative_to = process_relative_to


def resume_pending_merge(unpack_root, relative_to):
    """Finishes a move that was interrupted, if one is pending.

    Returns True when a pending move was found and completed.
    """
    relative_root = Path(unpack_root) / relative_to
    if not relative_root.is_dir():
        return False
    get_logger().info('Finishing the interrupted unpack of %s', relative_root)
    process_relative_to(Path(unpack_root), relative_to)
    return True
