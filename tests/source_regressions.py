"""Shared compiler harness for reviewed production-function fixtures."""
from pathlib import Path
import tempfile
from fork_review_regressions import ROOT, run as compile_run

def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

def run(name, code):
    with tempfile.TemporaryDirectory() as directory:
        compile_run(name, code, Path(directory))
