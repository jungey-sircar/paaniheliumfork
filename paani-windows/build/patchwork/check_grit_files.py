"""Checks that every .grd/.grdp/.xtb file in the tree is still well formed.

The Paani name substitution rewrites thousands of grit files in parallel.  If it
is interrupted a file can be left truncated, and that only shows up as an opaque
grit action failure much later in the build.  This parses each file once so the
damage is found before a build is started.

The walk is the substitution's own pruned walk (out/, .git/ and the ignored
directories never enumerated) so third_party grit sources are covered too, and
the parsing runs in worker processes because directory and file access on this
machine is the bottleneck, not CPU.
"""

import sys
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

UTILS = Path(__file__).resolve().parents[2] / 'utils'
sys.path.insert(0, str(UTILS))
sys.path.insert(0, str(UTILS.parent / 'helium-chromium' / 'utils'))

import name_substitution  # noqa: E402
import paani_name_substitution as paani_sub  # noqa: E402

SOURCE = UTILS.parent / 'build' / 'src'
EXTENSIONS = ['grd', 'grdp', 'xtb']
# Prebuilt toolchain blobs: enormous, and they hold no grit sources.
PRUNE = {'win_build_output'}


def candidates():
    ignored = set(name_substitution.IGNORE_DIRS) | PRUNE
    for path in paani_sub.get_substitutable_files(SOURCE, EXTENSIONS):
        if any(part in ignored for part in path.relative_to(SOURCE).parts):
            continue
        yield path


def parse(path):
    """Returns (path, problem) with problem None when the file is intact."""
    try:
        if path.stat().st_size == 0:
            return path, 'empty file'
        ElementTree.parse(path)
    except OSError as error:
        return path, f'unreadable: {error}'
    except ElementTree.ParseError as error:
        return path, f'malformed: {error}'
    return path, None


def main():
    files = list(candidates())
    print(f'parsing {len(files)} grit/xtb files', flush=True)
    broken = []
    with ProcessPoolExecutor(max_workers=8) as executor:
        for index, (path, problem) in enumerate(executor.map(parse, files), 1):
            if problem:
                broken.append((path, problem))
            if index % 1000 == 0:
                print(f'  {index}/{len(files)} parsed', flush=True)
    for path, reason in broken:
        print(f'BROKEN {path.relative_to(SOURCE)}: {reason}')
    if broken:
        print(f'{len(broken)} files need a restore from the Paani tree')
        return 1
    print(f'all {len(files)} grit/xtb files parse')
    return 0


if __name__ == '__main__':
    sys.exit(main())
