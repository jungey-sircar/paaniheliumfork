#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2026 The Paani Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Applies a quilt style patch series, and can resume an interrupted one.

The upstream helper aborts the whole series when a single patch fails, and it
fails on every patch that is already applied.  That is fatal here: the Helium
series has 403 patches and applying it takes minutes, so a crash in the
middle of it would leave the tree in a state that cannot be patched again.

The patches below are therefore applied one at a time, and a patch that turns
out to be applied already is skipped instead of failing the build.
"""

import subprocess
from pathlib import Path

from _common import get_logger

_COMMON_ARGS = ('-p1', '--ignore-whitespace', '--no-backup-if-mismatch',
                '--remove-empty-files')


def _run(patch_bin, patch_path, tree, *extra):
    """Runs the patch binary and returns its exit code and output."""
    cmd = [str(patch_bin), *_COMMON_ARGS, '-i', str(patch_path), '-d',
           str(tree), *extra]
    result = subprocess.run(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, universal_newlines=True)
    return result.returncode, result.stdout or ''


def is_applied(patch_bin, patch_path, tree):
    """Returns whether the patch is applied to the tree already."""
    code, output = _run(patch_bin, patch_path, tree, '--dry-run', '--reverse')
    return code == 0


def apply_series(patches_dir, tree, patch_bin_path):
    """Applies every patch of a series to the tree.

    Patches that are applied already are skipped.  Returns the number of
    patches that were applied.
    """
    logger = get_logger()
    series = [line.strip() for line in
              Path(patches_dir, 'series').read_text(encoding='utf-8').splitlines()]
    series = [line for line in series if line and not line.startswith('#')]
    applied = 0
    for number, name in enumerate(series, start=1):
        patch_path = Path(patches_dir, name)
        if not patch_path.exists():
            raise FileNotFoundError(f'{patch_path} is listed in the series but missing')
        if is_applied(patch_bin_path, patch_path, tree):
            logger.info('* Already applied %s (%d/%d)', name, number, len(series))
            continue
        logger.info('* Applying %s (%d/%d)', name, number, len(series))
        code, output = _run(patch_bin_path, patch_path, tree, '--forward')
        if code != 0:
            raise RuntimeError(f'{patch_path} failed with exit code {code}:\n{output}')
        applied += 1
    return applied
