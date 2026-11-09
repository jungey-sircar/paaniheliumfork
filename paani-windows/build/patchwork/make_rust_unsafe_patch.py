"""Flips `allow_unsafe` on and records the change as a quilt patch.

The crates below are pulled in by //third_party/rust/adblock but are not built
by upstream Chromium, so their generated BUILD.gn files still carry
`allow_unsafe = false` while their sources use `unsafe`.  rustc is then run
with `-F unsafe-code` and refuses to compile them.

The edits are made in the tree and captured into
patches/paani/windows/paani-adblock-rust-unsafe.patch, so that the tree can be
rebuilt from a clean unpack.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'rust_unsafe'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-adblock-rust-unsafe.patch'

# Reported by build/patchwork/scan_rust_unsafe.py.
CRATES = [
    'adblock/v0_13',
    'aho_corasick/v1',
    'arrayvec/v0_7',
    'base64/v0_22',
    'bitflags/v2',
    'flatbuffers/v25',
    'idna/v1',
    'percent_encoding/v2',
    'seahash/v4',
    'semver/v1',
    'serde/v1',
    'synstructure/v0_13',
    'thiserror_impl/v1',
    'yoke_derive/v0_8',
    'zerovec_derive/v0_11',
]

DESCRIPTION = '''Enables unsafe code for the crates of the ad blocker closure.

Paani builds the Brave adblock-rust engine, which depends on crates that
upstream Chromium vendors but never compiles.  Their generated BUILD.gn files
say `allow_unsafe = false`, so rustc is invoked with `-F unsafe-code` and
rejects the `unsafe` blocks in them.  The flag is turned off for exactly the
crates that //third_party/rust/adblock pulls in.
'''


def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    chunks = [DESCRIPTION]
    changed = 0
    for crate in CRATES:
        relative = Path('third_party') / 'rust' / crate / 'BUILD.gn'
        path = SOURCE / relative
        if not path.is_file():
            raise SystemExit(f'{relative} is missing')

        original = path.read_text(encoding='utf-8')
        backup = BACKUP / (crate.replace('/', '_') + '.BUILD.gn')
        if not backup.exists():
            backup.write_text(original, encoding='utf-8')
        else:
            original = backup.read_text(encoding='utf-8')

        if 'allow_unsafe = false' not in original:
            print(f'{relative}: no allow_unsafe = false, skipped')
            continue

        updated = original.replace('allow_unsafe = false', 'allow_unsafe = true')
        path.write_text(updated, encoding='utf-8')
        changed += 1

        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile='a/' + relative.as_posix(),
            tofile='b/' + relative.as_posix(),
            n=3,
        )
        chunks.append(''.join(diff))

    PATCH.write_text(''.join(chunks), encoding='utf-8', newline='\n')
    print(f'{changed} crates updated, patch written to {PATCH}')


if __name__ == '__main__':
    main()
