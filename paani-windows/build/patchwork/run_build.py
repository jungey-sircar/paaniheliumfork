"""Runs the Chromium build through siso (autoninja) and logs to the workspace.

The task runner in the desktop app writes its log to a temp directory that the
sandbox blocks, so the build output is streamed into build/logs/build.log.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import msvc_env

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
LOG = ROOT / 'build' / 'logs' / 'build.log'


def main(argv):
    # siso draws its progress bar with block characters, and the Windows
    # console defaults to cp1252, which cannot encode them. Without this the
    # streaming loop raises and the real build exit code is lost.
    sys.stdout.reconfigure(errors='replace')
    LOG.parent.mkdir(parents=True, exist_ok=True)
    env = msvc_env.build_environment()
    env['SISO_PATH'] = str(SOURCE / 'third_party' / 'siso' / 'cipd' / 'siso.exe')
    args = [sys.executable, r'third_party\depot_tools\autoninja.py'] + argv
    with LOG.open('w', encoding='utf-8', errors='replace') as log:
        proc = subprocess.Popen(args, cwd=str(SOURCE), env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        for line in proc.stdout:
            sys.stdout.write(line)
            log.write(line)
            log.flush()
        proc.wait()
    print('build exit code: %d' % proc.returncode)
    return proc.returncode


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
