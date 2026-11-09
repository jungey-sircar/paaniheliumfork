#!/usr/bin/env python3

# Copyright 2026 The Paani Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Paani brand substitution for GRIT resources and translations.

Helium's own name substitution has already run by the time this script is
invoked, so the source tree says "Helium" wherever Chromium said "Chrome" or
"Chromium".  This pass renames that brand token to "Paani".

Left untouched on purpose:

* "Chrome Web Store", "Chrome Remote Desktop" and "Chrome Root Program" --
  Helium protects them, and they name Google products rather than the
  browser itself.
* "Chromium" -- the name of the engine project.  Upstream keeps it in the
  licence text and in the project links, and so do we.
* Copyright headers -- only the text of <message> and <translation> elements
  is rewritten, never XML comments or file headers.
* Pref names such as "helium.services.bangs" -- those are on-disk storage
  keys, not user-visible text.  Renaming them would invalidate existing
  profiles for no benefit.

The fingerprint bookkeeping is the same as upstream's: a <message> whose text
changes gets a new GRIT fingerprint, and the matching <translation> ids in
the .xtb files are remapped so that translations keep working.
"""

import argparse
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import name_substitution
import name_substitution_utils as util

PAANI_REPLACEMENT_REGEXES_STR = [
    # The internal WebUI scheme.
    (r'(\b)helium://', r'\1paani://'),
    # The brand name.  The lookahead keeps compound identifiers such as
    # "HeliumMiddleClickAutoscroll" intact.
    (r'\bHelium(?!\w)', r'Paani'),
]

PAANI_REPLACEMENT_REGEXES = [
    (re.compile(pattern), replacement)
    for pattern, replacement in PAANI_REPLACEMENT_REGEXES_STR
]


def use_paani_table():
    """Points the shared substitution helpers at the Paani table.

    The helpers read the table from the module globals, and every worker
    process re-imports this module, so the table has to be installed from
    inside the workers as well as in the parent.
    """
    util.REPLACEMENT_REGEXES = PAANI_REPLACEMENT_REGEXES


def replacement_sanity():
    """Checks that the replacement regexes behave as intended."""
    before_after = [
        ('chrome://about', 'chrome://about'),
        ('Helium', 'Paani'),
        ('helium://settings', 'paani://settings'),
        ('HeliumMiddleClickAutoscroll', 'HeliumMiddleClickAutoscroll'),
        ('Chromium Authors', 'Chromium Authors'),
        ('Chrome Web Store', 'Chrome Web Store'),
        ('The Helium Authors', 'The Paani Authors'),
    ]

    for source, expected in before_after:
        use_paani_table()
        modified, match = util.replace_text(source)
        assert modified == expected, f"sanity: {modified} != {expected}"


def get_substitutable_files(tree, exts, progress=None):
    """Finds the candidate files, with the same exclusions as Helium's walk.

    Two differences from name_substitution.get_substitutable_files(), both pure
    performance: the directories under "out" are pruned from the walk instead of
    being enumerated and skipped one by one, and the ignored directories are
    pruned rather than descended into.  The set of files yielded is identical --
    upstream skips every file in those subtrees anyway -- but a built tree has
    enough entries under out\\Default that enumerating them costs more than the
    whole substitution pass.  "progress", when given, is called with the number
    of entries seen so far, because on this machine directory enumeration runs
    at a few hundred entries per second and the pass looks wedged while it runs.
    """
    out = tree / 'out'
    ignored = name_substitution.IGNORE_DIRS
    seen = 0

    for root, dirs, files in os.walk(tree):
        root_path = Path(root)
        if root_path == out:
            # Upstream looks at files sitting directly in "out", but never at
            # what is below it, so only the children are dropped here.
            dirs.clear()
        else:
            dirs[:] = [name for name in dirs if name not in ignored]

        seen += len(dirs) + len(files)
        if progress is not None:
            progress(seen)

        if out in root_path.parents or any(name in root_path.parts for name in ignored):
            continue

        for filename in files:
            if filename.startswith('.'):
                continue
            ext = filename.split('.')[-1].lower()
            if ext not in exts:
                continue
            yield root_path / filename


XML_DECLARATION_RE = re.compile(r"^<\?xml[^>]*\?>\n")


def reserialise(original_text, replaced_text):
    """Keeps the prolog of the original file.

    util.replace_grit_tree() re-serialises with ElementTree, which always
    prepends an XML declaration.  Grit does not care, but the declaration is not
    inert elsewhere: components/helium_onboarding/util/generate-i18n.mts parses
    its .grdp with fast-xml-parser in preserveOrder mode, where the declaration
    becomes the first node and the root element lookup fails with
    "expected <grit-part> root element".  Upstream never trips over this because
    its pass rewrites Chrome to Helium and the onboarding strings already said
    Helium, so that file was never re-serialised -- renaming Helium to Paani is
    the first pass that touches it.
    """
    if not original_text.startswith("<?xml"):
        return XML_DECLARATION_RE.sub('', replaced_text, count=1)
    return replaced_text


def substitute_grit_file(args):
    """Replaces strings in a .grd/.grdp file and reports the fingerprint map."""
    path, tree, save_original, dry_run = args
    use_paani_table()
    arcname = str(path.relative_to(tree))

    with open(path, 'r', encoding='utf-8') as file:
        original_text = file.read()

    text = original_text.replace('&#36;', '!!dollar-sign-literal!!')
    replaced, fp_map = util.replace_grit_tree(text)
    if not fp_map:
        return None

    print(f"Paani: replaced strings in {arcname}")
    replaced = reserialise(original_text,
                           replaced.replace('!!dollar-sign-literal!!', '&#36;'))
    if not dry_run:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(replaced)

    return ((arcname, original_text) if save_original else None, fp_map)


def substitute_xtb_file(args):
    """Replaces strings in an .xtb file and remaps the translation ids."""
    path, tree, fp_map, save_original, dry_run = args
    use_paani_table()
    arcname = str(path.relative_to(tree))

    with open(path, 'r', encoding='utf-8') as file:
        original_text = file.read()

    text = original_text.replace('&#36;', '!!dollar-sign-literal!!')
    replaced = util.replace_xtb_tree(text, fp_map)
    if not replaced:
        return None

    print(f"Paani: replaced strings in {arcname}")
    replaced = replaced.replace('!!dollar-sign-literal!!', '&#36;')
    if not dry_run:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(replaced)

    return ((arcname, original_text) if save_original else None, )


def do_substitution(tree, workers, dry_run=False):
    """Performs the Paani name substitution over all candidate files."""
    use_paani_table()
    util.add_grit_to_path(tree)

    last_report = [0.0]

    def progress(seen):
        now = time.monotonic()
        if now - last_report[0] >= 30:
            last_report[0] = now
            print(f'Paani: scanning source tree, {seen} entries seen...', flush=True)

    # One walk for both file kinds.  The translations are processed after the
    # messages because they need the fingerprint map, but the paths themselves
    # do not change while the pass runs, so a second enumeration of the tree
    # would only cost time.
    grit_exts, xtb_exts = {'grd', 'grdp'}, {'xtb'}
    grit_files, xtb_files = [], []
    for path in get_substitutable_files(tree, grit_exts | xtb_exts, progress):
        ext = path.name.split('.')[-1].lower()
        (grit_files if ext in grit_exts else xtb_files).append(path)

    print(f'Paani: found {len(grit_files)} .grd files to process', flush=True)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        file_args = [(path, tree, False, dry_run) for path in grit_files]
        results = executor.map(substitute_grit_file, file_args)
        modified_files = [r for r in results if r is not None]

    fp_map = util.merge_fp_maps(modified_files)

    print(f'Paani: found {len(xtb_files)} .xtb files to process', flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        file_args = [(path, tree, fp_map, False, dry_run) for path in xtb_files]
        results = executor.map(substitute_xtb_file, file_args)
        modified_files += [r for r in results if r is not None]

    print(f'Paani: modified {len(modified_files)} files', flush=True)
    return len(modified_files)


def main():
    """CLI entrypoint"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', metavar='source_tree', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=os.cpu_count())
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    replacement_sanity()
    do_substitution(args.t, args.workers, args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
