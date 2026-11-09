#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Moves the Paani layer behind the Helium layer in paani-windows/build.py.

The Paani patches are generated from the finished Helium tree, so they have to
be applied to exactly that state.  Doing them before the substitution and the
resource steps would apply them to a tree that the generator never saw.
"""
import pathlib
import sys

BUILD = pathlib.Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build.py')

REPLACEMENTS = []

REPLACEMENTS.append((
"""        if not args.dev:
            # Apply patches
            # First, the Helium series, which carries the ungoogled-chromium
            # patches, and then the Windows specific ones.
            if not _is_done('patched-helium'):
                paani_patches.apply_series(
                    _ROOT_DIR / 'helium-chromium' / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                paani_patches.apply_series(
                    _ROOT_DIR / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                _mark_done('patched-helium')
            # Finally the Paani patches, which build on top of the Helium ones.
            # They live in their own series so that the upstream series stays
            # untouched and a baseline build is a plain Helium build.
            if not args.baseline and not _is_done('patched-paani'):
                _apply_paani_patches(source_tree)
                _mark_done('patched-paani')

        else:""",
"""        if not args.dev:
            # Apply the Helium series, which carries the ungoogled-chromium
            # patches, and then the Windows specific ones.
            if not _is_done('patched-helium'):
                paani_patches.apply_series(
                    _ROOT_DIR / 'helium-chromium' / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                paani_patches.apply_series(
                    _ROOT_DIR / 'patches', source_tree,
                    source_tree / _PATCH_BIN_RELPATH)
                _mark_done('patched-helium')

        else:"""))

REPLACEMENTS.append((
"""                # Append translations
                i18n_apply.apply_translations(source_tree)
                _mark_done('substituted')

            # Rename the Helium brand to Paani.  This has to run after the
            # translations above, otherwise the fingerprints of the freshly
            # inserted <translation> elements would not match the renamed
            # <message> elements.
            if not args.baseline and not _is_done('substituted-paani'):
                _apply_paani_name_substitution(source_tree)
                _mark_done('substituted-paani')

        # Set version
        if not _is_done('versioned'):
            version_parts = helium_version.get_version_parts(_ROOT_DIR / 'helium-chromium', _ROOT_DIR)
            chrome_version_path = source_tree / "chrome" / "VERSION"
            helium_version.check_existing_version(chrome_version_path)
            with open(chrome_version_path, "a") as f:
                for name, version in version_parts.items():
                    helium_version.append_version(f, name, version)
            _mark_done('versioned')

        if not args.baseline and not _is_done('versioned-paani'):
            _apply_paani_version(source_tree)
            _mark_done('versioned-paani')

        # Copy resources
        # First, the Windows specific and the common Helium assets.
        if not _is_done('resourced'):
            _copy_helium_resources(source_tree)
            _mark_done('resourced')

        # Then the Paani branding, which has to be applied last so that it
        # wins over the Helium assets copied above.
        if not args.baseline and not _is_done('resourced-paani'):
            _apply_paani_resources(source_tree)
            _mark_done('resourced-paani')

        _configure_remoteexec(source_tree)""",
"""                # Append translations
                i18n_apply.apply_translations(source_tree)
                _mark_done('substituted')

        # Set version
        if not _is_done('versioned'):
            version_parts = helium_version.get_version_parts(_ROOT_DIR / 'helium-chromium', _ROOT_DIR)
            chrome_version_path = source_tree / "chrome" / "VERSION"
            helium_version.check_existing_version(chrome_version_path)
            with open(chrome_version_path, "a") as f:
                for name, version in version_parts.items():
                    helium_version.append_version(f, name, version)
            _mark_done('versioned')

        # Copy resources
        # First, the Windows specific and the common Helium assets.
        if not _is_done('resourced'):
            _copy_helium_resources(source_tree)
            _mark_done('resourced')

        # The Paani layer sits on top of the finished Helium tree, because the
        # Paani patches are generated from exactly that state.
        if not args.dev and not args.baseline:
            if not _is_done('patched-paani'):
                _apply_paani_patches(source_tree)
                _mark_done('patched-paani')

            # Rename the Helium brand to Paani.  This has to run after the
            # translations above, otherwise the fingerprints of the freshly
            # inserted <translation> elements would not match the renamed
            # <message> elements.
            if not _is_done('substituted-paani'):
                _apply_paani_name_substitution(source_tree)
                _mark_done('substituted-paani')

            if not _is_done('versioned-paani'):
                _apply_paani_version(source_tree)
                _mark_done('versioned-paani')

            # The Paani branding has to be applied last so that it wins over
            # the Helium assets copied above.
            if not _is_done('resourced-paani'):
                _apply_paani_resources(source_tree)
                _mark_done('resourced-paani')

        _configure_remoteexec(source_tree)"""))


def main():
    raw = BUILD.read_bytes()
    crlf = b'\r\n' in raw
    text = raw.decode('utf-8')
    if crlf:
        text = text.replace('\r\n', '\n')
    for index, (old, new) in enumerate(REPLACEMENTS, start=1):
        count = text.count(old)
        if count != 1:
            print('replacement %d matched %d times' % (index, count))
            print(old.splitlines()[0][:110])
            return 1
        text = text.replace(old, new)
    if crlf:
        text = text.replace('\n', '\r\n')
    BUILD.write_bytes(text.encode('utf-8'))
    print('build.py reordered (%d replacements)' % len(REPLACEMENTS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
