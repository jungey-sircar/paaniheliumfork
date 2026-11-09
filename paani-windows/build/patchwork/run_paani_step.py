"""Runs one step of the Paani layer without starting a build.

build.py only exposes the whole layer, which makes it impossible to apply the
sources and patches, check them with gn and a narrow build, and only then apply
the name substitution and the branding assets.  This runs a single step and
writes the same marker file, so a later `build.py --paani-only` skips it.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import msvc_env

spec = importlib.util.spec_from_file_location('paani_build', ROOT / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

SOURCE = ROOT / 'build' / 'src'
LOG = ROOT / 'build' / 'logs'


def run_gn():
    """Runs `gn gen` with the toolchain environment and keeps the output."""
    LOG.mkdir(parents=True, exist_ok=True)
    args = [str(SOURCE / 'buildtools' / 'win' / 'gn.exe'), 'gen', 'out/Default',
            '--fail-on-unused-args']
    with (LOG / 'gn.log').open('w', encoding='utf-8', errors='replace') as log:
        proc = subprocess.Popen(args, cwd=str(SOURCE),
                                env=msvc_env.build_environment(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding='utf-8', errors='replace')
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
            log.flush()
        code = proc.wait()
    if code:
        raise SystemExit('gn gen failed with exit code %d' % code)


STEPS = {
    'sources': ('copied-paani-sources', lambda: build._copy_paani_sources(SOURCE)),
    'patches': ('patched-paani', lambda: build._apply_paani_patches(SOURCE)),
    'substitute': ('substituted-paani',
                   lambda: build._apply_paani_name_substitution(SOURCE)),
    'version': ('versioned-paani', lambda: build._apply_paani_version(SOURCE)),
    'resources': ('resourced-paani', lambda: build._apply_paani_resources(SOURCE)),
    'gn': (None, run_gn),
}


def main(argv):
    if not argv or argv[0] not in STEPS:
        print('usage: run_paani_step.py <%s>' % '|'.join(STEPS))
        return 2
    marker, action = STEPS[argv[0]]
    action()
    if marker:
        build._mark_done(marker)
    print('%s done' % argv[0])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
