"""Portable behavior tests; game/DLL/Papyrus runtime validation is separate."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='sexlab-tests-') as tmp:
    for name in ('assignment_matching','request_sequence','core_utilities','decode_bounds'):
        binary=Path(tmp)/name
        subprocess.run([os.environ.get('CXX','clang++'),'-std=c++20','-O2','-pthread',str(ROOT/'tests'/f'{name}.cpp'),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
for name in ('full_fourth_review','full_third_review','full_second_review','full_review_regressions','ml_session_regressions','strip_regressions','source_regressions','recognition_regressions','lifecycle_regressions','csv_schema','native_contracts','ml_export'):
    subprocess.run([sys.executable,str(ROOT/'tests'/f'{name}.py')],check=True)
print('PASS: all portable tests; DLL and game runtime were not tested')
