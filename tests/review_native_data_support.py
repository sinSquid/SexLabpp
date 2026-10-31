"""Small production-function extraction harness for native data regressions."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(relative, signature):
    source = (ROOT / relative).read_text(encoding='utf-8-sig')
    start = source.index(signature)
    parens, brace = 0, start
    while True:
        char = source[brace]
        if char == '(':
            parens += 1
        elif char == ')':
            parens -= 1
        elif char == '{' and parens == 0:
            break
        brace += 1
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


def run(name, code, flags=()):
    with tempfile.TemporaryDirectory(prefix='sexlab-native-data-') as temp:
        cpp, binary = Path(temp) / (name + '.cpp'), Path(temp) / name
        cpp.write_text(code, encoding='utf-8')
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', '-pthread',
                        '-I' + str(ROOT / 'src'),
                        '-I' + str(ROOT / 'lib/CommonLibSSE-NG/include'),
                        *flags, str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=30)
    print('PASS:', name, flush=True)
