"""Proves Paani's pruned substitution walk matches Helium's original one.

utils/paani_name_substitution.get_substitutable_files() prunes the out
directory and the ignored directories out of os.walk() instead of enumerating
and skipping them.  Pruning is only equivalent if nothing that upstream yields
is hidden behind a pruned directory, so this compares the two generators
entry-for-entry on a synthetic tree that exercises every rule and on real
subtrees of the source tree.
"""

import sys
import tempfile
from pathlib import Path

UTILS = Path(__file__).resolve().parents[2] / 'utils'
HELIUM_UTILS = UTILS.parent / 'helium-chromium' / 'utils'
sys.path.insert(0, str(UTILS))
sys.path.insert(0, str(HELIUM_UTILS))

import name_substitution  # noqa: E402  (helium-chromium/utils, pristine)
import paani_name_substitution as paani_sub  # noqa: E402

EXTS = ['grd', 'grdp', 'xtb']

# (relative path, expected in the candidate set, why)
SYNTHETIC = [
    ('chrome/app/generated_resources.grd', True, 'ordinary file'),
    ('ui/webui/strings.grdp', True, 'grdp extension'),
    ('chrome/app/en-US-Formal.xtb', True, 'xtb extension'),
    ('chrome/app/EN-US-XTB.GRDTOP', False, 'unknown extension'),
    ('out/root_level.grd', True, 'directly in out, which upstream still reads'),
    ('out/Default/gen/nested.grd', False, 'below out'),
    ('out/Default/a/b/c/d/e/f/deep.grd', False, 'deeply below out'),
    ('ash/policy.grd', False, 'ignored directory name'),
    ('remoting/strings/it.xtb', False, 'ignored directory name'),
    ('chrome/testdata/fixture.grd', False, 'ignored directory name'),
    ('chrome/testdata/deeper/still.grd', False, 'below an ignored directory'),
    ('chrome/app/.hidden.grd', False, 'dot-prefixed file'),
    ('chrome/app/sub/.grd', False, 'dot-prefixed file'),
    ('third_party/boring/strings.grd', True, 'third party is not excluded'),
]


def build_synthetic(root):
    for relative, _expected, _why in SYNTHETIC:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('<placeholder/>', encoding='utf-8')


def check_synthetic():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_synthetic(root)
        mine = sorted(p.relative_to(root) for p in paani_sub.get_substitutable_files(root, EXTS))
        theirs = sorted(p.relative_to(root) for p in name_substitution.get_substitutable_files(root, EXTS))
        if mine != theirs:
            print(f'mismatch: only mine={set(mine) - set(theirs)} '
                  f'only upstream={set(theirs) - set(mine)}')
            return False

        expected = sorted(Path(r) for r, wanted, _ in SYNTHETIC if wanted)
        if mine != expected:
            print(f'both walks agree, but not with the documented rule set:\n'
                  f'  got      {mine}\n  expected {expected}')
            return False

        print(f'synthetic tree: {len(mine)} candidates, both walks agree, '
              f'rules as documented')
        return True


def check_real_subtree(name):
    tree = UTILS.parent / 'build' / 'src'
    subtree = tree / name
    if not subtree.is_dir():
        print(f'{name}: missing, skipped')
        return True
    mine = list(paani_sub.get_substitutable_files(subtree, EXTS))
    theirs = list(name_substitution.get_substitutable_files(subtree, EXTS))
    if sorted(mine) != sorted(theirs):
        only_mine = set(mine) - set(theirs)
        only_theirs = set(theirs) - set(mine)
        print(f'{name}: MISMATCH  only-mine={len(only_mine)} only-upstream={len(only_theirs)}')
        for path in list(only_mine)[:5] + list(only_theirs)[:5]:
            print(f'    {path}')
        return False
    print(f'{name}: {len(mine)} candidates, both walks agree')
    return True


def main():
    paani_sub.use_paani_table()
    ok = check_synthetic()
    # Subtrees chosen because they hold real .grd files and are small enough to
    # walk twice; the out/ pruning cannot be exercised here (a subtree of the
    # tree has no out/ child), which is what the synthetic tree is for.
    for subtree in ('chrome/app', 'ui/webui', 'components/resources'):
        ok = check_real_subtree(subtree) and ok
    print('PARITY OK' if ok else 'PARITY FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
