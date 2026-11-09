"""Reports the vendored Rust crates that need `allow_unsafe`.

Pulling `//third_party/rust/adblock` into the build drags in a dependency
closure that Chromium never compiled, so several of the generated crate
targets are missing the `allow_unsafe = true` that their sources need.  The
build stops at the first failure, which makes discovering them one compile at
a time far too slow; this walks the closure and reports all of them at once.

Usage:
    python build/patchwork/scan_rust_unsafe.py //third_party/rust/adblock/v0_13:lib
"""

import re
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / 'build' / 'src'
CRATES_DIR = SOURCE / 'third_party' / 'rust'

DEP_RE = re.compile(r'"(//third_party/rust/[^"]+:[^"]+)"')
ALLOW_UNSAFE_RE = re.compile(r'^\s*allow_unsafe\s*=\s*true', re.MULTILINE)
CRATE_ROOT_RE = re.compile(r'crate_root\s*=\s*(\S+)')
SOURCES_RE = re.compile(r'sources\s*=\s*\[(.*?)\]', re.DOTALL)
QUOTED_RE = re.compile(r'"([^"]+)"')
ALLOW_ATTR_RE = re.compile(r'#!\[allow\(\s*unsafe_code\s*\)\]|#\[allow\(\s*unsafe_code\s*\)\]')


def read(path):
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''


def label_to_build_gn(label):
    # //third_party/rust/percent_encoding/v2:lib -> .../percent_encoding/v2/BUILD.gn
    without_scheme = label[2:]
    target = without_scheme.split(':')[1]
    directory = without_scheme.split(':')[0]
    return SOURCE / directory / 'BUILD.gn', target


def crate_sources(text):
    """Returns the source files listed by a cargo_crate() target."""
    paths = []
    root_match = CRATE_ROOT_RE.search(text)
    if root_match:
        value = root_match.group(1).strip()
        # `crate_root = "src/lib.rs"` or a concatenated string expression.
        for quoted in QUOTED_RE.findall(value):
            if quoted.lstrip('/').startswith('third_party/rust/'):
                paths.append(quoted)
    sources_match = SOURCES_RE.search(text)
    if sources_match:
        for entry in QUOTED_RE.findall(sources_match.group(1)):
            if entry.lstrip('/').startswith('third_party/rust/'):
                paths.append(entry)
    return paths


def uses_unsafe(paths):
    for entry in paths:
        path = SOURCE / entry.lstrip('/')
        text = read(path)
        if not text:
            continue
        if re.search(r'\bunsafe\b', text) and not ALLOW_ATTR_RE.search(text):
            return str(path.relative_to(SOURCE))
    return None


def walk(root_label):
    pending = [root_label]
    seen = set()
    missing = []
    while pending:
        label = pending.pop()
        if label in seen:
            continue
        seen.add(label)
        build_gn, target = label_to_build_gn(label)
        if not build_gn.is_file():
            continue
        text = read(build_gn)
        deps = DEP_RE.findall(text)
        pending.extend(deps)

        if ALLOW_UNSAFE_RE.search(text):
            continue
        offending = uses_unsafe(crate_sources(text))
        if offending:
            missing.append((label, str(build_gn.relative_to(SOURCE)), offending))
    return missing


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '//third_party/rust/adblock/v0_13:lib'
    missing = walk(root)
    print('visited %d targets' % len(seen_count(root)))
    for label, build_gn, offending in sorted(missing):
        print('%s\n    BUILD.gn: %s\n    unsafe in: %s' % (label, build_gn, offending))
    print('%d crate targets need allow_unsafe = true' % len(missing))
    return 0


def seen_count(root):
    # Kept for the summary line only.
    pending, seen = [root], set()
    while pending:
        label = pending.pop()
        if label in seen:
            continue
        seen.add(label)
        build_gn, _ = label_to_build_gn(label)
        if build_gn.is_file():
            pending.extend(DEP_RE.findall(read(build_gn)))
    return seen


if __name__ == '__main__':
    sys.exit(main())
