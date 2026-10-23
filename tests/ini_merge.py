"""Run production INI merging without loading optional model-training packages."""
import ast
import configparser
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'scripts/ML/export.py').read_text())
tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in ('_ensure_ini_path', 'unify_ini_files')]
namespace = {'Path': Path, 'configparser': configparser}
exec(compile(tree, 'scripts/ML/export.py', 'exec'), namespace)
merge = namespace['unify_ini_files']
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source, output = root / 'a.ini', root / 'z.ini'
    source.write_text('[profile]\nvalue=new\n')
    output.write_text('[profile]\nvalue=old\nkeep=yes\n[other]\nkey=retained\n')
    merge(root, output)
    result = configparser.ConfigParser()
    result.read(output)
    assert result['profile']['value'] == 'new'
    assert result['profile']['keep'] == 'yes'
    assert result['other']['key'] == 'retained'
    before = output.read_bytes()
    merge(root, output)
    assert output.read_bytes() == before
    merge(output, output)
    assert output.read_bytes() == before
print('PASS: output inside input directory, retained settings, repeat and same-file merge')
