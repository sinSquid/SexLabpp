"""Exercise the owned translation updater against temporary files only."""
from pathlib import Path
import ast
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'dist/Interface/Translations/translate.py'
tree = ast.parse(SOURCE.read_text())
# Load definitions without invoking the old module's destructive top-level loop.
definitions = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
namespace = {}
exec(compile(ast.Module(body=definitions, type_ignores=[]), str(SOURCE), 'exec'), namespace)

with tempfile.TemporaryDirectory() as temporary:
    directory = Path(temporary)
    english = directory / 'SexLab_ENGLISH.txt'
    target = directory / 'SexLab_RUSSIAN.txt'
    target.write_text('\ufeff$kept translated\n# TODO: $new\n\n$new stale fallback\n', encoding='utf-16le')
    keys, _ = namespace['parse_file'](target)
    assert keys == {'$kept': '$kept translated\n'}, keys
    english.write_text('\ufeff$kept English\n$new new English\n$added added\n', encoding='utf-16le')
    namespace['en_keys'], namespace['en_lines'] = namespace['parse_file'](english)
    namespace['copy_new_keys'](target, namespace['en_lines'])
    expected = '\ufeff$kept translated\n# TODO: $new\n$new new English\n# TODO: $added\n$added added\n'
    assert target.read_text(encoding='utf-16le') == expected
    namespace['copy_new_keys'](target, namespace['en_lines'])
    assert target.read_text(encoding='utf-16le') == expected, 'rerun must be stable'
    original = target.read_bytes()
    with patch('os.replace', side_effect=OSError('simulated replace failure')):
        try:
            namespace['copy_new_keys'](target, namespace['en_lines'])
        except OSError:
            pass
        else:
            raise AssertionError('replace failure was hidden')
    assert target.read_bytes() == original, 'failed update truncated the translation'
    assert not list(directory.glob('*.tmp')), 'temporary file leaked'
    target.unlink()
    namespace['copy_new_keys'](target, namespace['en_lines'])
    assert target.exists(), 'missing translation should start with TODO fallback keys'
print('PASS: translation BOM, TODO gaps, stable merge, missing target and atomic failure')
