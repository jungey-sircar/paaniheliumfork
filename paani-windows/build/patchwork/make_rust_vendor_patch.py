"""Corrects vendored crate GN targets and records the changes as a patch.

`build/patchwork/check_rust_targets.py` compares every `third_party/rust` target
with the files it names, and `build/patchwork/check_rust_nightly.py` walks the ad
blocker's crate closure for crate-root `#![feature(...)]` gates.  Both found one
problem each, and both only show up once //third_party/rust/adblock drags these
crates into the build for the first time:

* `third_party/rust/thiserror/v1/BUILD.gn` declares a `private.rs` build-script
  output that thiserror 1.0.69's `build.rs` never writes (that is thiserror v2),
  which aborts the build-script step in `run_build_script.py`.
* `third_party/rust/flatbuffers/v25/BUILD.gn` is compiled with Chromium's global
  `--cfg nightly`, so its `#![cfg_attr(nightly, feature(trusted_len))]` is active
  while the default `disallow_unstable_features` config passes an empty
  `-Zallow-features=`, which rustc rejects with E0725.

The edits are made in the tree and captured into
patches/paani/windows/paani-rust-vendor.patch so a clean unpack rebuilds.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'rust_vendor'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-rust-vendor.patch'

# (crate label, text to find, replacement)
EDITS = [
    ('thiserror/v1', '  build_script_outputs = [ "private.rs" ]\n', ''),
    ('flatbuffers/v25',
     '  _configs_to_remove += []\n',
     '  _configs_to_remove += [\n'
     '    # `flatbuffers` has `#![cfg_attr(nightly, feature(trusted_len))]` in\n'
     '    # src/lib.rs, and Chromium always passes `--cfg nightly`, so that\n'
     '    # feature has to be reachable.  Upstream never compiles this crate, so\n'
     '    # the empty `-Zallow-features=` of the default config was never\n'
     '    # noticed; //third_party/rust/adblock is the first consumer.\n'
     '    "//build/config/compiler:disallow_unstable_features",\n'
     '  ]\n'),
]

DESCRIPTION = '''Fixes two vendored Rust targets that the ad blocker builds first.

//third_party/rust/adblock is the first consumer of //third_party/rust/thiserror/v1
and //third_party/rust/flatbuffers/v25, and both generated BUILD.gn files describe
them in a way that only works while nothing compiles them.  thiserror v1 promises a
`private.rs` build-script output its build.rs does not produce - that is thiserror
v2 - so run_build_script.py aborts looking for the file.  flatbuffers enables
`feature(trusted_len)` under the nightly cfg that Chromium always sets, which the
default `disallow_unstable_features` config forbids with an empty
`-Zallow-features=`.
'''


def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    chunks = [DESCRIPTION]
    changed = 0
    for crate, old, new in EDITS:
        relative = Path('third_party') / 'rust' / crate / 'BUILD.gn'
        path = SOURCE / relative
        if not path.is_file():
            raise SystemExit(f'{relative} is missing')

        current = path.read_text(encoding='utf-8')
        backup = BACKUP / (crate.replace('/', '_') + '.BUILD.gn')
        if not backup.exists():
            backup.write_text(current, encoding='utf-8')
            original = current
        else:
            original = backup.read_text(encoding='utf-8')

        if old not in original:
            if new in original:
                print(f'{relative}: already applied')
            else:
                print(f'{relative}: marker {old.strip()!r} not found')
            continue

        updated = original.replace(old, new, 1)
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
    print(f'{changed} target(s) updated, patch written to {PATCH}')


if __name__ == '__main__':
    main()
