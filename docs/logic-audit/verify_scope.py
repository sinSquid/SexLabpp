"""Inventory every owned executable source, without treating enumeration as review."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EXTENSIONS = {'.cpp', '.h', '.py', '.psc', '.lua', '.def', '.ps1'}
EXCLUDED = {
    'src/Util/Premutation.h': 'Bundled Howard Hinnant/Boost implementation; application usage remains in scope',
    'lib/ImGui/SKSEMenuFramework.h': 'Bundled SKSE Menu Framework interface; application usage remains in scope',
}


def main():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    files, excluded, syntax_errors = [], [], []
    production = set()
    for relative in sorted(set(paths)):
        path = ROOT / relative
        if not path.is_file() or not (path.suffix in EXTENSIONS or relative.startswith('.github/workflows/') and path.suffix in {'.yml', '.yaml'}):
            continue
        data = path.read_bytes()
        record = {'path': relative, 'sha256': hashlib.sha256(data).hexdigest(), 'lines': len(data.splitlines())}
        if relative in EXCLUDED:
            excluded.append(record | {'reason': EXCLUDED[relative]})
            continue
        auxiliary = relative.startswith(('tests/', 'docs/logic-audit/', '.github/'))
        record['scope'] = 'auxiliary' if auxiliary else 'production'
        record['evidence'] = ['file_enumerated_and_hashed']
        if not auxiliary:
            production.add(relative)
        if path.suffix == '.py':
            try:
                ast.parse(data.decode('utf-8-sig'), filename=relative)
                record['evidence'].append('python_ast_parsed')
            except (SyntaxError, UnicodeError) as error:
                syntax_errors.append({'path': relative, 'error': str(error)})
        files.append(record)
    inventory = json.loads((OUT / 'inventory.json').read_text())
    missing = sorted(production - {entry['path'] for entry in inventory['files']})
    report = {'status': 'scope_enumeration_only', 'files': files, 'excluded': excluded,
              'external_dependencies': [{'path': 'lib/CommonLibSSE-NG', 'reason': 'Git submodule implementation outside owned-source scope; owned callers remain in scope; checkout has no readable source here'}],
              'production_missing_from_function_inventory': missing, 'python_syntax_errors': syntax_errors,
              'limitation': 'Enumeration, hashing and AST parsing do not verify runtime logic or prove every call chain.'}
    (OUT / 'full-scan-scope.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'production': len(production), 'auxiliary': len(files) - len(production),
                      'excluded': len(excluded), 'missing_inventory': missing, 'syntax_errors': syntax_errors}))
    if missing or syntax_errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
