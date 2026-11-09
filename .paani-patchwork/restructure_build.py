#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Restructures paani-windows/build.py so that the preparation phase resumes.

The file uses CRLF line endings, so the replacements are done on a normalized
copy and written back with the original endings.
"""
import pathlib
import sys

BUILD = pathlib.Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build.py')

REPLACEMENTS = []

REPLACEMENTS.append((
"""import patches
import paani_name_substitution""",
"""import patches
import paani_name_substitution
import paani_patches"""))

REPLACEMENTS.append((
'''def _apply_paani_patches(source_tree):
    """Applies the Paani patch series on top of the Helium patches."""
    patches.apply_patches(
        patches.generate_patches_from_series(
            _ROOT_DIR / 'patches' / 'paani', resolve=True),
        source_tree,
        patch_bin_path=(source_tree / _PATCH_BIN_RELPATH)
    )''',
'''def _apply_paani_patches(source_tree):
    """Applies the Paani patch series on top of the Helium patches."""
    paani_patches.apply_series(
        _ROOT_DIR / 'patches' / 'paani',
        source_tree,
        source_tree / _PATCH_BIN_RELPATH
    )'''))

REPLACEMENTS.append((
'''def _apply_paani_version(source_tree):
    """Appends the PAANI_* version entries to chrome/VERSION."""
    chrome_version_path = source_tree / 'chrome' / 'VERSION'
    paani_version_parts = paani_version.get_version_parts(_ROOT_DIR)
    paani_version.check_existing_version(chrome_version_path)
    with open(chrome_version_path, 'a') as f:
        for name, version in paani_version_parts.items():
            paani_version.append_version(f, name, version)''',
'''def _apply_paani_version(source_tree):
    """Appends the PAANI_* version entries to chrome/VERSION."""
    chrome_version_path = source_tree / 'chrome' / 'VERSION'
    if 'PAANI_' in chrome_version_path.read_text(encoding=ENCODING):
        # The version was added by an earlier run.
        return
    paani_version_parts = paani_version.get_version_parts(_ROOT_DIR)
    paani_version.check_existing_version(chrome_version_path)
    with open(chrome_version_path, 'a') as f:
        for name, version in paani_version_parts.items():
            paani_version.append_version(f, name, version)'''))

REPLACEMENTS.append((
'''def _apply_paani_layer(source_tree):
    """Applies the whole Paani layer on top of a prepared Helium tree."""
    _apply_paani_patches(source_tree)
    _apply_paani_name_substitution(source_tree)
    _apply_paani_version(source_tree)
    _apply_paani_resources(source_tree)''',
'''def _apply_paani_layer(source_tree):
    """Applies the whole Paani layer on top of a prepared Helium tree."""
    if not _is_done('patched-paani'):
        _apply_paani_patches(source_tree)
        _mark_done('patched-paani')
    if not _is_done('substituted-paani'):
        _apply_paani_name_substitution(source_tree)
        _mark_done('substituted-paani')
    if not _is_done('versioned-paani'):
        _apply_paani_version(source_tree)
        _mark_done('versioned-paani')
    if not _is_done('resourced-paani'):
        _apply_paani_resources(source_tree)
        _mark_done('resourced-paani')'''))

REPLACEMENTS.append((
"""        pending = []
        for name in components:
            if _already_unpacked(name):
                continue
            if name == 'chromium' and (source_tree / 'BUILD.gn').exists():
                # The prepared Chromium archive was unpacked before the state
                # of the unpack was recorded.
                _mark_unpacked(name)
                continue
            pending.append(name)
        skipped = [name for name in components if name not in pending]
        if skipped:
            get_logger().info('Already unpacked, skipping: %s',
                              ', '.join(skipped))
        if pending:
            downloads.unpack_downloads(download_info, downloads_cache, pending,
                                       source_tree, extractors)
            for name in pending:
                _mark_unpacked(name)
        prune_binaries.prune_dirs(source_tree, False, None, keep_build_dependencies=True)
        pruning_list = _ROOT_DIR / 'helium-chromium' / 'pruning.list'
        prune_list = tuple(filter(len, pruning_list.read_text(encoding=ENCODING).splitlines()))
        missing_files = prune_binaries.prune_files(
            source_tree, prune_list, keep_build_dependencies=True)
        if missing_files:
            get_logger().info('Skipped %d pruning entries absent from this source tree',
                              len(missing_files))""",
"""        pending = []
        for name in components:
            if _is_done('unpacked-' + name):
                continue
            if name == 'chromium' and (source_tree / 'BUILD.gn').exists():
                # The prepared Chromium archive was unpacked before the state
                # of the unpack was recorded.
                _mark_done('unpacked-' + name)
                continue
            pending.append(name)
        skipped = [name for name in components if name not in pending]
        if skipped:
            get_logger().info('Already unpacked, skipping: %s',
                              ', '.join(skipped))
        if pending:
            downloads.unpack_downloads(download_info, downloads_cache, pending,
                                       source_tree, extractors)
            for name in pending:
                _mark_done('unpacked-' + name)
        if not _is_done('pruned'):
            prune_binaries.prune_dirs(source_tree, False, None, keep_build_dependencies=True)
            pruning_list = _ROOT_DIR / 'helium-chromium' / 'pruning.list'
            prune_list = tuple(filter(len, pruning_list.read_text(encoding=ENCODING).splitlines()))
            missing_files = prune_binaries.prune_files(
                source_tree, prune_list, keep_build_dependencies=True)
            if missing_files:
                get_logger().info('Skipped %d pruning entries absent from this source tree',
                                  len(missing_files))
            _mark_done('pruned')"""))

REPLACEMENTS.append((
"""        if not args.dev:
            # Apply patches
            # First, ungoogled-chromium-patches
            patches.apply_patches(
                patches.generate_patches_from_series(_ROOT_DIR / 'helium-chromium' / 'patches', resolve=True),
                source_tree,
                patch_bin_path=(source_tree / _PATCH_BIN_RELPATH)
            )
            # Then Windows-specific patches
            patches.apply_patches(
                patches.generate_patches_from_series(_ROOT_DIR / 'patches', resolve=True),
                source_tree,
                patch_bin_path=(source_tree / _PATCH_BIN_RELPATH)
            )
            # Finally the Paani patches, which build on top of the Helium ones.
            # They live in their own series so that the upstream series stays
            # untouched and a baseline build is a plain Helium build.
            if not args.baseline:
                _apply_paani_patches(source_tree)

        else:""",
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

        else:"""))

REPLACEMENTS.append((
"""        if not args.dev:
            # Substitute domains
            domain_substitution_list = _ROOT_DIR / 'helium-chromium' / 'domain_substitution.list'
            domain_substitution.apply_substitution(
                _ROOT_DIR / 'helium-chromium' / 'domain_regex.list',
                domain_substitution_list,
                source_tree,
                None
            )

            # Substitute names
            name_substitution.do_substitution(
                source_tree,
                tarpath=None,
                workers=min(32, os.cpu_count()),
                dry_run=False
            )

            # Append translations
            i18n_apply.apply_translations(source_tree)

            # Rename the Helium brand to Paani.  This has to run after the
            # translations above, otherwise the fingerprints of the freshly
            # inserted <translation> elements would not match the renamed
            # <message> elements.
            if not args.baseline:
                _apply_paani_name_substitution(source_tree)""",
"""        if not args.dev:
            if not _is_done('substituted'):
                # Substitute domains
                domain_substitution_list = _ROOT_DIR / 'helium-chromium' / 'domain_substitution.list'
                domain_substitution.apply_substitution(
                    _ROOT_DIR / 'helium-chromium' / 'domain_regex.list',
                    domain_substitution_list,
                    source_tree,
                    None
                )

                # Substitute names
                name_substitution.do_substitution(
                    source_tree,
                    tarpath=None,
                    workers=min(32, os.cpu_count()),
                    dry_run=False
                )

                # Append translations
                i18n_apply.apply_translations(source_tree)
                _mark_done('substituted')

            # Rename the Helium brand to Paani.  This has to run after the
            # translations above, otherwise the fingerprints of the freshly
            # inserted <translation> elements would not match the renamed
            # <message> elements.
            if not args.baseline and not _is_done('substituted-paani'):
                _apply_paani_name_substitution(source_tree)
                _mark_done('substituted-paani')"""))

REPLACEMENTS.append((
"""        # Set version
        version_parts = helium_version.get_version_parts(_ROOT_DIR / 'helium-chromium', _ROOT_DIR)
        chrome_version_path = source_tree / "chrome" / "VERSION"
        helium_version.check_existing_version(chrome_version_path)
        with open(chrome_version_path, "a") as f:
            for name, version in version_parts.items():
                helium_version.append_version(f, name, version)

        if not args.baseline:
            _apply_paani_version(source_tree)""",
"""        # Set version
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
            _mark_done('versioned-paani')"""))

REPLACEMENTS.append((
"""        # Copy resources
        # First, generate and copy Windows-specific resources
        generate_resources.generate_resources(
            _ROOT_DIR / 'resources' / 'generate_resources.txt',
            _ROOT_DIR / 'resources'
        )

        replace_resources.copy_resources(
            _ROOT_DIR / 'resources' / 'platform_resources.txt',
            _ROOT_DIR / 'resources',
            source_tree
        )

        # Then common helium-chromium resources
        generate_resources.generate_resources(
            _ROOT_DIR / 'helium-chromium' / 'resources' / 'generate_resources.txt',
            _ROOT_DIR / 'helium-chromium' / 'resources'
        )

        replace_resources.copy_resources(
            _ROOT_DIR / 'helium-chromium' / 'resources' / 'helium_resources.txt',
            _ROOT_DIR / 'helium-chromium' / 'resources',
            source_tree
        )

        # Finally the Paani branding, which has to be applied last so that it
        # wins over the Helium assets copied above.
        if not args.baseline:
            _apply_paani_resources(source_tree)""",
"""        # Copy resources
        # First, the Windows specific and the common Helium assets.
        if not _is_done('resourced'):
            _copy_helium_resources(source_tree)
            _mark_done('resourced')

        # Then the Paani branding, which has to be applied last so that it
        # wins over the Helium assets copied above.
        if not args.baseline and not _is_done('resourced-paani'):
            _apply_paani_resources(source_tree)
            _mark_done('resourced-paani')"""))

REPLACEMENTS.append((
'''def _state_marker(name):''',
'''def _copy_helium_resources(source_tree):
    """Copies the Windows and Helium branding resources into the tree."""
    generate_resources.generate_resources(
        _ROOT_DIR / 'resources' / 'generate_resources.txt',
        _ROOT_DIR / 'resources'
    )

    replace_resources.copy_resources(
        _ROOT_DIR / 'resources' / 'platform_resources.txt',
        _ROOT_DIR / 'resources',
        source_tree
    )

    generate_resources.generate_resources(
        _ROOT_DIR / 'helium-chromium' / 'resources' / 'generate_resources.txt',
        _ROOT_DIR / 'helium-chromium' / 'resources'
    )

    replace_resources.copy_resources(
        _ROOT_DIR / 'helium-chromium' / 'resources' / 'helium_resources.txt',
        _ROOT_DIR / 'helium-chromium' / 'resources',
        source_tree
    )


def _state_marker(name):'''))


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
    print('build.py restructured (%d replacements)' % len(REPLACEMENTS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
