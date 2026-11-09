#!/usr/bin/env python3

# Copyright 2026 The Paani Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Paani version numbers, injected into the Chromium build tree.

Upstream Helium appends HELIUM_* entries to chrome/VERSION and threads them
through chrome/version.gni, chrome/common/chrome_version.h.in and the Windows
version resources.  Paani does the same with PAANI_* entries, so that the
browser reports its own version instead of Helium's.
"""

import argparse
from pathlib import Path

VERSION_KEYS = ('MAJOR', 'MINOR', 'PATCH', 'PLATFORM')


def read_version_parts(path):
    """Reads the MAJOR/MINOR/PATCH/PLATFORM entries of a version file."""
    parts = {}
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, sep, value = line.partition('=')
            if not sep:
                continue
            if key in VERSION_KEYS:
                parts[key] = value.strip()
    missing = [key for key in VERSION_KEYS if key not in parts]
    if missing:
        raise ValueError(f'{path}: missing version entries: {", ".join(missing)}')
    return parts


def get_version_parts(platform_tree):
    """Returns the PAANI_* version parts."""
    parts = read_version_parts(platform_tree / 'paani_version.txt')
    return {f'PAANI_{key}': parts[key] for key in VERSION_KEYS}


def check_existing_version(path):
    """Verifies that the Paani version has not been added yet."""
    with open(path, 'r', encoding='utf-8') as file:
        if 'PAANI_' in file.read():
            raise ValueError('file already contains Paani versioning')


def append_version(file, name, version):
    """Appends a version part to the Chromium VERSION file."""
    file.write(f'{name}={version}\n')


def main():
    """CLI entrypoint"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--chromium-tree', type=Path)
    parser.add_argument('--print', action=argparse.BooleanOptionalAction)
    args = parser.parse_args()

    version_parts = get_version_parts(args.tree)
    if args.print:
        print('.'.join(version_parts.values()))
    else:
        chrome_version_path = args.chromium_tree / 'chrome' / 'VERSION'
        check_existing_version(chrome_version_path)
        with open(chrome_version_path, 'a', encoding='utf-8') as file:
            for name, version in version_parts.items():
                append_version(file, name, version)


if __name__ == '__main__':
    main()
