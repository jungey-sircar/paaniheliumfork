"""Checks every vendored Rust GN target against the files it claims to build.

The ad blocker drags a large `third_party/rust` closure into the build, and each
crate is described by a generated `BUILD.gn`.  A target that names a source file
that is not in the tree, or a build-script output its `build.rs` never writes,
fails deep inside a multi-hour build.  This walks the whole closure once and
reports every mismatch in seconds, so the fixes can be batched into one patch.
"""

import re
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'src'
RUST_DIR = SOURCE / 'third_party' / 'rust'

BUILD_ROOT_RE = re.compile(r'^\s*build_root\s*=\s*(?:"([^"]+)"|(\S+))', re.M)
SOURCES_RE = re.compile(r'^\s*(?:sources|build_sources)\s*=\s*\[(.*?)\]', re.M | re.S)
OUTPUTS_RE = re.compile(r'^\s*build_script_outputs\s*=\s*\[(.*?)\]', re.M | re.S)
STRING_RE = re.compile(r'"([^"]+)"')


def gn_path(value):
    """Resolves a `//dir/file` GN label into a filesystem path."""
    if not value.startswith('//'):
        return None
    relative = value[2:]
    if ':' in relative:
        return None
    return SOURCE / relative


def literal_strings(text):
    """Returns the string literals found in a chunk of GN source."""
    return STRING_RE.findall(text)


def check_target(build_gn):
    """Returns the problems found in one crate's BUILD.gn."""
    problems = []
    text = build_gn.read_text(encoding='utf-8', errors='replace')

    sources = []
    for match in SOURCES_RE.finditer(text):
        sources.extend(literal_strings(match.group(1)))
    # `$gen_dir` and friends are not resolvable here; only `//` paths are checked.
    for entry in sources:
        path = gn_path(entry) if entry.startswith('//') else None
        if path is not None and not path.is_file():
            problems.append('%s: source %s does not exist' % (build_gn, entry))

    outputs = []
    for match in OUTPUTS_RE.finditer(text):
        outputs.extend(literal_strings(match.group(1)))
    if not outputs:
        return problems

    root_match = BUILD_ROOT_RE.search(text)
    root = None
    if root_match:
        root = gn_path(root_match.group(1) or '')
    if root is None or not root.is_file():
        problems.append('%s: declares build_script_outputs %s but has no readable '
                        'build script' % (build_gn, outputs))
        return problems

    script = root.read_text(encoding='utf-8', errors='replace')
    for output in outputs:
        # The script has to name the file it writes, or write into a directory
        # it then hands over; either way the name appears in the source.
        if output.split('.')[0] not in script and output not in script:
            problems.append('%s: build script %s never mentions output %s'
                            % (build_gn, root.relative_to(SOURCE), output))
    return problems


def main():
    if not RUST_DIR.is_dir():
        print('no %s' % RUST_DIR)
        return 1
    problems = []
    targets = 0
    patterns = ('*/v*/BUILD.gn', '*/v*/*/BUILD.gn')
    seen = set()
    for pattern in patterns:
        for build_gn in sorted(RUST_DIR.glob(pattern)):
            if build_gn in seen:
                continue
            seen.add(build_gn)
            targets += 1
            problems.extend(check_target(build_gn))
    print('checked %d vendored rust targets under %s' % (targets, RUST_DIR))
    for problem in problems:
        print('PROBLEM %s' % problem.replace(str(SOURCE) + '\\', ''))
    print('%d problem(s) found' % len(problems))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
