#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2025 The Helium Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.

# Copyright (c) 2019 The ungoogled-chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Helium build script for Windows
"""

import sys
import time
import argparse
import filecmp
import os
import shutil
import subprocess
import ctypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'helium-chromium' / 'utils'))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'utils'))
import downloads
import domain_substitution
import i18n_apply
import name_substitution
import helium_version
import generate_resources
import replace_resources
import paani_icons
import prune_binaries
import patches
import paani_name_substitution
import paani_patches
import paani_unpack
import paani_version
from _common import ENCODING, USE_REGISTRY, ExtractorEnum, get_logger
sys.path.pop(0)
sys.path.pop(0)

_ROOT_DIR = Path(__file__).resolve().parent
_PATCH_BIN_RELPATH = Path('third_party/git/usr/bin/patch.exe')
_PYBIN_DIR = _ROOT_DIR / 'build' / 'pybin'
# The leading directory that the prepared Chromium archives are stripped of.
_CHROMIUM_ARCHIVE_DIRS = ('chromium-156.0.8078.79',)
# Where the state of the preparation steps is recorded.
_STATE_DIR = _ROOT_DIR / 'build' / 'state'


def _get_vcvars_path(name='64'):
    """
    Returns the path to the corresponding vcvars*.bat path

    As of VS 2017, name can be one of: 32, 64, all, amd64_x86, x86_amd64
    """
    vswhere_exe = '%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe'
    result = subprocess.run(
        '"{}" -products * -prerelease -latest -property installationPath'.format(vswhere_exe),
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True)
    vcvars_path = Path(result.stdout.strip(), 'VC/Auxiliary/Build/vcvars{}.bat'.format(name))
    if not vcvars_path.exists():
        raise RuntimeError(
            'Could not find vcvars batch script in expected location: {}'.format(vcvars_path))
    return vcvars_path


def _get_visual_studio_path():
    """
    Returns the installation path of the newest Visual Studio.

    Chromium's vs_toolchain.py only looks for Visual Studio 2022 and newer
    under "%ProgramFiles%", but the 2022 build tools install into
    "%ProgramFiles(x86)%".  The vs2022_install variable tells the build
    system where the installation actually is.
    """
    vswhere_exe = '%ProgramFiles(x86)%\\Microsoft Visual Studio\\Installer\\vswhere.exe'
    result = subprocess.run(
        '"{}" -products * -prerelease -latest -property installationPath'.format(vswhere_exe),
        shell=True,
        check=True,
        stdout=subprocess.PIPE,
        universal_newlines=True)
    installation_path = Path(result.stdout.strip())
    if not installation_path.exists():
        raise RuntimeError(
            'Visual Studio installation not found: {}'.format(installation_path))
    return installation_path


def _check_windows_sdk(source_tree):
    """
    Stops early when the Windows SDK that Chromium pins is not installed.

    Chromium 156 requires the Windows SDK 10.0.28000.0.  Older SDKs are not a
    usable substitute: 10.0.22621 for instance predates the
    WINCRYPT_USE_SYMBOL_PREFIX guard in wincrypt.h, so the X509_NAME macros of
    CryptoAPI collide with BoringSSL's headers, and it does not declare
    KeyCredentialStatus_AlgorithmNotSupported, which crypto/ calls.  Paani
    therefore patches nothing in build/ and expects the SDK to be installed;
    see the "Setting up Visual Studio" section of README.md.

    The required version is read from the tree instead of being repeated here,
    so that this check follows upstream instead of drifting from it.
    """
    vs_toolchain = source_tree / 'build' / 'vs_toolchain.py'
    if not vs_toolchain.exists():
        return None
    required = None
    for line in vs_toolchain.read_text(encoding=ENCODING).splitlines():
        if line.startswith('SDK_VERSION = '):
            required = line.split('=', 1)[1].strip().strip("'\"")
            break
    if required is None:
        raise RuntimeError(
            'Could not read SDK_VERSION from %s; upstream changed the format'
            % vs_toolchain)

    kits = (Path(os.environ.get('ProgramFiles(x86)',
                                 r'C:\Program Files (x86)')) /
            'Windows Kits' / '10' / 'Include')
    installed = sorted(entry.name for entry in kits.iterdir()
                       if (entry / 'um' / 'dwmapi.h').exists()) \
        if kits.is_dir() else []
    if required not in installed:
        raise RuntimeError(
            'Windows SDK %s is required by Chromium and is not installed. '
            'Found: %s. Install it from '
            'https://learn.microsoft.com/en-us/windows/apps/windows-sdk/downloads, '
            'with the Debugging Tools for Windows component. See README.md.'
            % (required, ', '.join(installed) or 'nothing'))
    return required


def _read_gn_flags(path):
    """
    Reads a GN flag file into a dictionary.

    A flag that is set in more than one file keeps the value of the last
    file, and a flag that is set twice in the same file keeps the value of
    the last line.
    """
    values = {}
    for line in path.read_text(encoding=ENCODING).splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep:
            continue
        values[key.strip()] = value.strip()
    return values


def _python3_shim_is_usable(path):
    if not path.exists():
        return False
    result = subprocess.run(
        [str(path), '-c', 'import sys, json; print("%d.%d" % sys.version_info[:2])'],
        capture_output=True,
        encoding=ENCODING,
    )
    return result.returncode == 0 and result.stdout.strip() == '%d.%d' % sys.version_info[:2]


def _ensure_python3_shim():
    """
    Returns the path of the `python3.exe` that the build scripts are run with.

    Chromium's code generation actions call `python3` by name.  When the Python
    installation only ships `python.exe`, that name resolves to whichever other
    interpreter is on PATH - on this machine the MSYS2 one, whose handling of
    the batch wrappers made every `third_party/dom_distiller_js` protoc plugin
    action fail.  The README asks for a copy or a symlink next to the real
    interpreter; a symlink needs Developer Mode or admin rights, so this is the
    copy, placed in a directory that is put first on the build PATH below.
    """
    shim = _PYBIN_DIR / 'python3.exe'
    if not _python3_shim_is_usable(shim):
        _PYBIN_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(sys.executable, shim)
        if not _python3_shim_is_usable(shim):
            raise RuntimeError(
                'Could not prepare a usable %s from %s. Install Python 3.11+ '
                'and make sure its directory is on PATH; see README.md.'
                % (shim, sys.executable))
    return shim


def _build_env_commands():
    """Returns the cmd.exe statements that set up the environment of a build."""
    return [
        'call "%s" >nul' % _get_vcvars_path(),
        'set DEPOT_TOOLS_WIN_TOOLCHAIN=0',
        'set "vs2022_install=%s"' % _get_visual_studio_path(),
        'set "GYP_MSVS_OVERRIDE_PATH=%s"' % _get_visual_studio_path(),
        'set "PATH=%s;%s;%%PATH%%"' % (
            _ensure_python3_shim().parent,
            Path(sys.executable).resolve().parent,
        ),
    ]


def _run_build_process(*args, **kwargs):
    """
    Runs the subprocess with the correct environment variables for building
    """
    cmd_input = _build_env_commands()
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\n')
    subprocess.run(('cmd.exe', '/k'),
                   input='\n'.join(cmd_input),
                   check=True,
                   encoding=ENCODING,
                   **kwargs)


def _run_build_process_timeout(*args, timeout):
    """
    Runs the subprocess with the correct environment variables for building
    """
    cmd_input = _build_env_commands()
    cmd_input.append(' '.join(map('"{}"'.format, args)))
    cmd_input.append('exit\n')
    with subprocess.Popen(('cmd.exe', '/k'), encoding=ENCODING, stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP) as proc:
        proc.stdin.write('\n'.join(cmd_input))
        proc.stdin.close()
        try:
            proc.wait(timeout)
            if proc.returncode != 0:
                raise RuntimeError('Build failed!')
        except subprocess.TimeoutExpired:
            print('Sending keyboard interrupt')
            for _ in range(3):
                ctypes.windll.kernel32.GenerateConsoleCtrlEvent(1, proc.pid)
                time.sleep(1)
            try:
                proc.wait(10)
            except:
                proc.kill()
            sys.exit(42)


def _make_tmp_paths():
    """Creates TMP and TEMP variable dirs so ninja won't fail"""
    tmp_path = Path(os.environ['TMP'])
    if not tmp_path.exists():
        tmp_path.mkdir()
    tmp_path = Path(os.environ['TEMP'])
    if not tmp_path.exists():
        tmp_path.mkdir()


def _configure_remoteexec(source_tree):
    address = os.environ.get('SISO_REAPI_ADDRESS', '')
    instance = os.environ.get('SISO_REAPI_INSTANCE') or 'main'
    backend = ''
    if address:
        os.environ['SISO_REAPI_INSTANCE'] = instance
        backend = 'nativelink.star'

    subprocess.run([
        sys.executable, str(source_tree / 'build/config/siso/configure_siso.py'),
        '--rbe_instance=projects/rbe-chrome-untrusted/instances/default_instance',
        f'--reapi_address={address}',
        f'--reapi_instance={instance if address else ""}',
        f'--reapi_backend_config_path={backend}',
    ], check=True)


def _apply_paani_patches(source_tree):
    """Applies the Paani patch series on top of the Helium patches."""
    paani_patches.apply_series(
        _ROOT_DIR / 'patches' / 'paani',
        source_tree,
        source_tree / _PATCH_BIN_RELPATH
    )


def _apply_paani_name_substitution(source_tree):
    """Renames the Helium brand to Paani in the GRIT resources.

    This has to run after the translations were inserted, otherwise the
    fingerprints of the freshly inserted <translation> elements would not
    match the renamed <message> elements.
    """
    paani_name_substitution.do_substitution(
        source_tree,
        workers=min(32, os.cpu_count()),
        dry_run=False
    )


def _apply_paani_version(source_tree):
    """Appends the PAANI_* version entries to chrome/VERSION."""
    chrome_version_path = source_tree / 'chrome' / 'VERSION'
    if 'PAANI_' in chrome_version_path.read_text(encoding=ENCODING):
        # The version was added by an earlier run.
        return
    paani_version_parts = paani_version.get_version_parts(_ROOT_DIR)
    paani_version.check_existing_version(chrome_version_path)
    with open(chrome_version_path, 'a') as f:
        for name, version in paani_version_parts.items():
            paani_version.append_version(f, name, version)


def _apply_paani_resources(source_tree):
    """Installs the Paani branding assets, over the Helium ones."""
    paani_icons.generate(
        _ROOT_DIR / 'resources' / 'paani' / 'branding' / 'app_icon' /
        'master_waterdrop.png',
        _ROOT_DIR / 'resources' / 'paani' / 'branding',
        _ROOT_DIR / 'resources' / 'generated',
    )

    generate_resources.generate_resources(
        _ROOT_DIR / 'resources' / 'paani_generate_resources.txt',
        _ROOT_DIR / 'resources'
    )

    replace_resources.copy_resources(
        _ROOT_DIR / 'resources' / 'paani_resources.txt',
        _ROOT_DIR / 'resources',
        source_tree
    )


def _copy_paani_sources(source_tree):
    """Copies the Paani specific sources into the Chromium tree.

    The sources live in `paani-windows/src` so that they are kept under
    version control of this repository instead of being mixed into the
    Chromium checkout.  They are copied verbatim, the tree is not patched.
    """
    source_root = _ROOT_DIR / 'src'
    if not source_root.is_dir():
        return

    copied = 0
    for source in sorted(source_root.rglob('*')):
        if source.is_dir():
            continue
        relative = source.relative_to(source_root)
        target = source_tree / relative
        if target.exists() and target.stat().st_size == source.stat().st_size:
            if filecmp.cmp(source, target, shallow=False):
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied += 1
    print(f'Paani sources: {copied} file(s) changed in {source_tree}')


def _copy_helium_resources(source_tree):
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


def _state_marker(name):
    """Returns the path of the marker that records a finished step."""
    return _STATE_DIR / (name + '.done')


def _is_done(name):
    """Returns whether a preparation step was already finished."""
    return _state_marker(name).exists()


def _mark_done(name):
    """Records that a preparation step was finished."""
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_marker(name).write_text('done', encoding=ENCODING)


def _resume_pending_unpack(source_tree):
    """Finishes an archive move that a previous run left half done."""
    for relative_to in _CHROMIUM_ARCHIVE_DIRS:
        pending = source_tree / relative_to
        if not pending.is_dir():
            continue
        try:
            paani_unpack.resume_pending_merge(source_tree, relative_to)
        except OSError as exc:
            get_logger().warning('Could not clear %s: %s', pending, exc)
        if pending.is_dir():
            # The name is needed by the next archive, so the leftovers are
            # moved out of the way.
            moved = source_tree / (relative_to + '.pending')
            try:
                pending.rename(moved)
                get_logger().info('Moved the leftover %s to %s', pending, moved)
            except OSError as exc:
                get_logger().error('Could not move %s out of the way: %s',
                                   pending, exc)
                raise


def _apply_paani_layer(source_tree):
    """Applies the whole Paani layer on top of a prepared Helium tree."""
    if not _is_done('copied-paani-sources'):
        _copy_paani_sources(source_tree)
        _mark_done('copied-paani-sources')
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
        _mark_done('resourced-paani')


def main():
    """CLI Entrypoint"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--7z-path',
        dest='sevenz_path',
        default=USE_REGISTRY,
        help=('Command or path to 7-Zip\'s "7z" binary. If "_use_registry" is '
              'specified, determine the path from the registry. Default: %(default)s'))
    parser.add_argument(
        '--winrar-path',
        dest='winrar_path',
        default=USE_REGISTRY,
        help=('Command or path to WinRAR\'s "winrar.exe" binary. If "_use_registry" is '
              'specified, determine the path from the registry. Default: %(default)s'))
    parser.add_argument(
        '-j',
        type=int,
        dest='thread_count',
        help=('Number of CPU threads to use for compiling'))
    parser.add_argument(
        '--ci',
        type=int,
    )
    parser.add_argument(
        '--arm',
        action='store_true'
    )
    sources = parser.add_mutually_exclusive_group()
    sources.add_argument(
        '--tarball', dest='tarball', action='store_true',
        help='Download prepared Chromium archives (default for x64)')
    sources.add_argument(
        '--clone', dest='tarball', action='store_false',
        help='Clone Chromium and prepare dependencies with gclient (default for ARM64)')
    parser.set_defaults(tarball=None)
    parser.add_argument(
        '--dev',
        action='store_true'
    )
    parser.add_argument(
        '--baseline',
        action='store_true',
        help=('Build the unmodified Helium upstream instead of Paani. The Paani '
              'patches, the Paani name substitution and the Paani resources are '
              'all skipped, which produces the reference build used for the '
              'performance comparison.'))
    parser.add_argument(
        '--profile',
        choices=('official', 'personal'),
        default='official',
        help=('Build profile. "official" is the upstream Helium release '
              'configuration: an official build with ThinLTO and PGO. '
              '"personal" drops the official-build flag and PGO, which removes '
              'the ThinLTO link step; that needs a lot less RAM and disk but '
              'produces a slightly less optimized binary. Always build the '
              'baseline and the Paani tree with the same profile so the '
              'performance comparison stays fair.'))
    parser.add_argument(
        '--paani-only',
        action='store_true',
        help=('Apply only the Paani layer (patches, name substitution, version '
              'and resources) to a tree that has already been prepared by a '
              'previous run, then rebuild. This turns a baseline tree into the '
              'Paani tree without unpacking the source again.'))
    args = parser.parse_args()
    if args.tarball is None:
        args.tarball = not args.arm
    if args.tarball and args.arm:
        parser.error('the prepared Windows archive targets x64; use --clone for ARM64')

    # Set common variables
    source_tree = _ROOT_DIR / 'build' / 'src'
    downloads_cache = _ROOT_DIR / 'build' / 'download_cache'
    if os.environ.get('SISO_REAPI_ADDRESS'):
        os.environ['RBE_service_no_security'] = 'true'

    prepare_tree = not args.ci or not (source_tree / 'BUILD.gn').exists()

    if args.paani_only:
        if args.baseline:
            parser.error('--paani-only and --baseline are mutually exclusive')
        if not (source_tree / 'BUILD.gn').exists():
            parser.error('--paani-only needs a tree that was already prepared; '
                         'run a full build first.')
        _apply_paani_layer(source_tree)
    elif prepare_tree:
        # Setup environment
        source_tree.mkdir(parents=True, exist_ok=True)
        downloads_cache.mkdir(parents=True, exist_ok=True)
        _make_tmp_paths()

        # Extractors
        extractors = {
            ExtractorEnum.SEVENZIP: args.sevenz_path,
            ExtractorEnum.WINRAR: args.winrar_path,
        }

        download_configs = [
            _ROOT_DIR / 'downloads.ini',
            _ROOT_DIR / 'helium-chromium' / 'deps.ini',
        ]
        if args.tarball:
            download_configs = [
                _ROOT_DIR / 'helium-chromium' / 'downloads.ini',
                _ROOT_DIR / 'downloads.x64.ini',
            ] + download_configs
        else:
            subprocess.run([
                sys.executable, str(_ROOT_DIR / 'helium-chromium' / 'utils' / 'clone.py'),
                '-o', str(source_tree), '-p', 'win-arm64' if args.arm else 'win64',
            ], check=True)

        get_logger().info('Downloading required files...')
        download_info = downloads.DownloadInfo(download_configs)
        downloads.retrieve_downloads(download_info, downloads_cache, None, True)
        try:
            downloads.check_downloads(download_info, downloads_cache, None)
        except downloads.HashMismatchError as exc:
            get_logger().error('File checksum does not match: %s', exc)
            parser.exit(1)
        get_logger().info('Unpacking downloads...')
        # The move that strips the leading directory of the source archives
        # fails whenever a background scanner holds one of the freshly
        # written directories, so it is done with a retry.
        paani_unpack.install()
        _resume_pending_unpack(source_tree)
        components = [name for name, _ in download_info.properties_iter()]
        # The archives are unpacked in place, so a component that an earlier
        # run already unpacked is skipped.  Unpacking the two gigabyte
        # Chromium archives again would cost half an hour and another chance
        # for the file locks that the move has to survive.
        pending = []
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
            _mark_done('pruned')

        if not args.dev:
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

        else:
            print("Apply patches using quilt, then press Enter")
            input()

        # Remote Windows compiles use a separate Linux compiler on workers.
        # Apply its extraction patch before downloading, and substitute domains after.
        if os.environ.get('SISO_REAPI_ADDRESS'):
            subprocess.run([
                sys.executable, str(source_tree / 'tools/clang/scripts/update.py'),
                '--host-os=linux',
                '--output-dir=' + str(source_tree / 'third_party/llvm-build/Release+Asserts_linux'),
            ], check=True)

        if not args.dev:
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
            if not _is_done('copied-paani-sources'):
                _copy_paani_sources(source_tree)
                _mark_done('copied-paani-sources')

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

        _configure_remoteexec(source_tree)

    _check_windows_sdk(source_tree)

    if not args.ci or not (source_tree / 'out/Default').exists():
        # Output args.gn
        (source_tree / 'out/Default').mkdir(parents=True, exist_ok=True)
        gn_values = _read_gn_flags(_ROOT_DIR / 'helium-chromium' / 'flags.gn')
        windows_values = _read_gn_flags(_ROOT_DIR / 'flags.windows.gn')
        if args.arm:
            windows_values = {key: value.replace('x64', 'arm64')
                              for key, value in windows_values.items()}
        gn_values.update(windows_values)

        if args.dev:
            gn_values['chrome_pgo_phase'] = '0'
            gn_values['is_component_build'] = 'true'
        else:
            gn_values['is_official_build'] = 'true'

        if args.profile == 'personal':
            # is_official_build turns on ThinLTO on Windows, and the resulting
            # link of chrome.dll needs far more RAM than a typical desktop has
            # to spare.  PGO phase 2 adds two more full builds plus a training
            # run on top of that.  Both are dropped here; the baseline and the
            # Paani build use the same profile, so the comparison stays fair.
            gn_values['is_official_build'] = 'false'
            gn_values['chrome_pgo_phase'] = '0'

        if os.environ.get('SISO_REAPI_ADDRESS'):
            gn_values['use_remoteexec'] = 'true'
            # Precompiled modules are not portable across Windows/Linux hosts.
            gn_values['use_clang_modules'] = 'false'
        elif shutil.which('sccache'):
            gn_values['cc_wrapper'] = '"sccache"'

        winsparkle_ed_key = os.environ.get('WINSPARKLE_ED_KEY', '')
        authenticode_org = os.environ.get('WINSPARKLE_AUTHENTICODE_ORG', '')
        if winsparkle_ed_key and authenticode_org:
            gn_values['enable_winsparkle'] = 'true'
            gn_values['winsparkle_ed_key'] = '"%s"' % winsparkle_ed_key
            gn_values['winsparkle_authenticode_org'] = '"%s"' % authenticode_org

        (source_tree / 'out/Default/args.gn').write_text(
            ''.join('%s=%s\n' % (key, value)
                    for key, value in gn_values.items()),
            encoding=ENCODING)

    # Enter source tree to run build commands
    os.chdir(source_tree)

    if not args.ci or not os.path.exists('out\\Default\\build.ninja'):
        # Run gn gen
        _run_build_process(
            'buildtools\\win\\gn.exe', 'gen', 'out\\Default', '--fail-on-unused-args')

    # Ninja commandline
    os.environ.setdefault('SISO_PATH', str(source_tree / 'third_party/siso/cipd/siso.exe'))
    ninja_commandline = [sys.executable, 'third_party\\depot_tools\\autoninja.py']
    if args.thread_count is not None:
        ninja_commandline.append('-j')
        ninja_commandline.append(args.thread_count)
    ninja_commandline.append('-C')
    ninja_commandline.append('out\\Default')

    # Finish all release targets before signing. Siso can replace signed outputs
    # if it is invoked again to build their dependents (the mini installer).
    ninja_commandline.extend(['chrome', 'chromedriver', 'setup', 'mini_installer'])

    # Run ninja
    if args.ci:
        max_time = 5.5 * 60 * 60
        secs_spent = int(time.time()) - args.ci
        timeout = int(max_time - secs_spent)
        print(f"{timeout} seconds left for build")

        _run_build_process_timeout(*ninja_commandline, timeout=timeout)
    else:
        _run_build_process(*ninja_commandline)


if __name__ == '__main__':
    main()
