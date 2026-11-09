import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import importlib.util
spec = importlib.util.spec_from_file_location('paani_build', Path(__file__).resolve().parents[2] / 'build.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
args = sys.argv[1:]
b._run_build_process('buildtools\win\gn.exe', *args, cwd=str(b._ROOT_DIR / 'build' / 'src'))
