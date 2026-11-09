"""Runs plain ninja (not siso) against the Paani build tree.

siso spends minutes rebuilding its manifest and filesystem state after every
`gn gen`, which makes quick compile checks painful.  Plain ninja gives the
same result for the same .ninja files, so it is used for preflight builds.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import msvc_env

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
NINJA = SOURCE / 'third_party' / 'ninja' / 'ninja.exe'
LOG = ROOT / 'build' / 'logs' / 'ninja.log'


def main(argv):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    args = [str(NINJA), '-C', 'out/Default'] + argv
    with LOG.open('w', encoding='utf-8', errors='replace') as log:
        proc = subprocess.Popen(args, cwd=str(SOURCE),
                                env=msvc_env.build_environment(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
        proc.wait()
    print('ninja exit code: %d' % proc.returncode)
    return proc.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
