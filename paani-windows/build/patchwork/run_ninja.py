import os
import sys
from pathlib import Path
import importlib.util
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('paani_build', root / 'build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
source_tree = b._ROOT_DIR / 'build' / 'src'
os.environ.setdefault('SISO_PATH', str(source_tree / 'third_party/siso/cipd/siso.exe'))
args = sys.argv[1:]
b._run_build_process(sys.executable, r'third_party\depot_tools\autoninja.py', *args,
                     cwd=str(source_tree))
