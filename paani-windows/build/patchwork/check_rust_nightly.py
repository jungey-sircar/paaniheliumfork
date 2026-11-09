"""Reports crates whose build would need an unstable Rust feature.

Chromium passes `--cfg nightly` to every Rust target (because
`rustc_nightly_capability` is on) while the default configs pass an empty
`-Zallow-features=`, so a crate root that says
`#![cfg_attr(nightly, feature(x))]` fails with E0725 the first time anything
actually compiles that crate.  //third_party/rust/adblock is the first consumer
of several vendored crates, so this finds all of them at once instead of one
build failure at a time.
"""

import re
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src'
RUST_DIR = SOURCE / 'third_party' / 'rust'
VENDOR_DIR = RUST_DIR / 'chromium_crates_io' / 'vendor'

DEP_RE = re.compile(r'"//third_party/rust/([^"]+):lib"')
VENDOR_RE = re.compile(
    r'//third_party/rust/chromium_crates_io/vendor/([A-Za-z0-9_.-]+)')
# Inner attributes at crate scope: `#![feature(x)]` or
# `#![cfg_attr(<cfg>, feature(x))]` where the cfg is one Chromium always sets.
ALWAYS_ON_CFG = ('nightly', 'all()')
ATTR_RE = re.compile(
    r'^\s*#!\[(?:(?:cfg_attr\(\s*(?P<cfg>[a-z_!()\s&]+?)\s*,\s*)?)'
    r'feature\((?P<features>[a-z_ ,]+)\)\]', re.M)


def closure_of(root_crate):
    """Returns {crate label: BUILD.gn text} reachable through `:lib` deps."""
    pending = [root_crate]
    found = {}
    while pending:
        crate = pending.pop()
        if crate in found:
            continue
        build_gn = RUST_DIR / crate / 'BUILD.gn'
        if not build_gn.is_file():
            found[crate] = None
            continue
        text = build_gn.read_text(encoding='utf-8', errors='replace')
        found[crate] = text
        pending.extend(sorted(set(DEP_RE.findall(text))))
    return found


def main(argv):
    roots = argv or ['adblock/v0_13']
    problems = []
    total = 0
    for root in roots:
        crates = closure_of(root)
        total += len(crates)
        for crate, text in sorted(crates.items()):
            if text is None:
                problems.append('%s: no BUILD.gn' % crate)
                continue
            for vendor in sorted(set(VENDOR_RE.findall(text))):
                lib = VENDOR_DIR / vendor / 'src' / 'lib.rs'
                if not lib.is_file():
                    continue
                for match in ATTR_RE.finditer(lib.read_text(
                        encoding='utf-8', errors='replace')):
                    cfg = (match.group('cfg') or '').strip()
                    active_without_cfg = not cfg
                    active_with_nightly = any(
                        word in cfg for word in ALWAYS_ON_CFG)
                    if not (active_without_cfg or active_with_nightly):
                        continue
                    if 'disallow_unstable_features' in text:
                        continue  # The target already opts out of the ban.
                    problems.append(
                        '%s (%s): cfg=%r needs feature(s) %s' % (
                            crate, vendor, cfg or '<none>',
                            match.group('features').strip()))
    print('scanned %d crate targets from %s' % (total, ', '.join(roots)))
    for problem in problems:
        print('PROBLEM %s' % problem)
    print('%d problem(s)' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
