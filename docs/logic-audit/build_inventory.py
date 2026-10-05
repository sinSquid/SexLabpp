"""Rebuild an audit inventory; extraction is NOT evidence of manual review.
Run with Python plus tree-sitter, tree-sitter-cpp and tree-sitter-lua installed.
Review decisions bind to source hashes, so changed bodies revert to pending.
"""
from pathlib import Path
import ast
from collections import Counter
import hashlib
import json
import re
import subprocess
import tree_sitter as ts
import tree_sitter_cpp
import tree_sitter_lua

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
EXCLUDE = {'src/Util/Premutation.h': 'Howard Hinnant / Boost third-party implementation; audit application call contracts separately'}
EXTENSIONS = {'.cpp', '.h', '.py', '.psc', '.lua', '.def'}
PARSERS = {'.cpp': ts.Parser(ts.Language(tree_sitter_cpp.language())),
           '.lua': ts.Parser(ts.Language(tree_sitter_lua.language()))}
PARSERS['.h'] = PARSERS['.cpp']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def inventory():
    paths = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT).decode().split('\0')
    records, files, exclusions = [], [], []
    for relative in sorted(set(paths)):
        p = ROOT / relative
        if p.suffix not in EXTENSIONS or not p.is_file():
            continue
        if not (relative.startswith(('src/', 'scripts/', 'xmake/', 'dist/Source/Scripts/', 'dist/Sound/')) or relative in ('xmake.lua', 'dist/Interface/Translations/translate.py')):
            continue
        data = p.read_bytes()
        text = data.decode('utf-8-sig')
        if relative in EXCLUDE:
            exclusions.append({'path': relative, 'reason': EXCLUDE[relative], 'sha256': digest(data)})
            continue
        row = {'path': relative, 'lines': len(text.splitlines()), 'sha256': digest(data), 'parse_errors': [], 'functions': 0}
        entries = []
        if p.suffix in PARSERS:
            # Ignore calling-convention/attribute macros without moving source offsets.
            parse_data = data
            if p.suffix != '.lua':
                parse_data = re.sub(rb'\b(?:_NODISCARD|__stdcall|__fastcall|__thiscall)\b',
                                    lambda match: b' ' * len(match.group()), data)
            tree = PARSERS[p.suffix].parse(parse_data)
            for node in walk(tree.root_node):
                if node.type == 'ERROR' or node.is_missing:
                    row['parse_errors'].append({'line': node.start_point.row + 1, 'kind': node.type})
                if node.type not in ('function_definition', 'lambda_expression', 'function_declaration'):
                    continue
                if p.suffix != '.lua' and node.type == 'function_declaration':
                    continue
                declaration = node.child_by_field_name('declarator') or node.child_by_field_name('name')
                name = data[declaration.start_byte:declaration.end_byte].decode() if declaration else '<anonymous>'
                name = re.sub(r'\s+', ' ', name).strip()
                entries.append((node.start_point.row + 1, node.end_point.row + 1, name, node.type, data[node.start_byte:node.end_byte]))
        elif p.suffix == '.py':
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                    segment = ast.get_source_segment(text, node)
                    entries.append((node.lineno, node.end_lineno, getattr(node, 'name', '<lambda>'), type(node).__name__, segment.encode()))
        elif p.suffix == '.psc':
            # Preserve positions while masking comments, documentation and strings.
            def mask(match):
                return ''.join('\n' if c == '\n' else ' ' for c in match.group())
            clean = re.sub(r';/.*?/;|;[^\n]*|\{.*?\}|"(?:\\.|[^"\\])*"', mask, text, flags=re.S)
            pattern = re.compile(r'^\s*(?:(?:\w+)(?:\[\])?\s+)?(function|event)\s+(\w+)\s*\([^)]*\)[^\n]*', re.I | re.M)
            for match in pattern.finditer(clean):
                start = match.start() + len(match.group()) - len(match.group().lstrip())
                kind = 'native_contract' if re.search(r'\bnative\b', match.group(), re.I) else match[1].lower()
                end = match.end()
                if kind != 'native_contract':
                    ending = re.search(r'\bend' + match[1] + r'\b', clean[end:], re.I)
                    if ending is None:
                        row['parse_errors'].append({'line': clean.count('\n', 0, start) + 1, 'kind': 'missing end'})
                    else:
                        end += ending.end()
                entries.append((clean.count('\n', 0, start) + 1, clean.count('\n', 0, end) + 1, match[2], kind, text[start:end].encode()))
        for start, end, name, kind, body in sorted(entries, key=lambda e: (e[0], e[1], e[2])):
            records.append({'id': f'{relative}:{start}:{name}', 'path': relative, 'start': start, 'end': end,
                            'name': name, 'kind': kind, 'sha256': digest(body), 'status': 'pending',
                            'review': None})
        row['functions'] = len(entries)
        files.append(row)
    return files, records, exclusions


def main():
    files, records, exclusions = inventory()
    decision_path = OUT / 'decisions.json'
    decisions = json.loads(decision_path.read_text()) if decision_path.exists() else {}
    for row in records:
        decision = decisions.get(row['id'])
        if decision and decision.get('sha256') == row['sha256']:
            row['status'] = decision['status']
            row['review'] = decision
    progress_path = OUT / 'full-scan-progress.json'
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
    body_reads = progress.get('reviewed_files', {})
    read_paths = {row['path'] for row in files
                  if body_reads.get(row['path'], {}).get('sha256') == row['sha256']}
    for row in records:
        # Derived file-body evidence only. Do not replace per-function decisions or close contracts.
        row['body_read_this_pass'] = row['path'] in read_paths
        if row['body_read_this_pass']:
            row['body_read_evidence'] = 'full-scan-progress.json:reviewed_files:' + row['path']
    (OUT / 'inventory.json').write_text(json.dumps({'files': files, 'functions': records, 'excluded': exclusions}, ensure_ascii=False, indent=2) + '\n')
    reconciliation_path = OUT / 'parser-reconciliation.json'
    reconciliations = json.loads(reconciliation_path.read_text()) if reconciliation_path.exists() else {}
    diagnostic_files = [row for row in files if row['parse_errors']]
    reconciled = []
    for file in diagnostic_files:
        evidence = reconciliations.get(file['path'], {})
        definitions = [{key: row[key] for key in ('start', 'end', 'name', 'sha256')}
                       for row in records if row['path'] == file['path']]
        if (evidence.get('sha256') == file['sha256'] and evidence.get('diagnostics') == file['parse_errors']
                and evidence.get('definitions') == definitions
                and evidence.get('expected_definition_entries') == len(definitions)
                and evidence.get('omitted_definitions') == []):
            reconciled.append(file['path'])
    counts = Counter(row['status'] for row in records)
    report = ['# 本轮覆盖状态', '', '**本体覆盖与逐函数审查结论分别统计；全调用链闭环尚未完成。**', '',
              f'生产文件：{len(files)}；源码行：{sum(x["lines"] for x in files)}；已提取函数/事件/声明条目：{len(records)}。', '',
              f'当前指纹匹配的本轮完整本体读取：{len(read_paths)}/{len(files)} 文件；{sum(row["body_read_this_pass"] for row in records)}/{len(records)} 提取条目在已读本体内（由文件记录派生，非逐函数验证）。', '',
              '逐函数结论台账状态（旧记录不代表本轮全链验证）：' + ', '.join(f'{key}={value}' for key, value in sorted(counts.items())) + '。', '',
              f'解析诊断文件已人工对账：{len(reconciled)}/{len(diagnostic_files)}（按文件及定义指纹校验）。详见 parser-reconciliation.json。', '',
              '条目分母为实现/事件/lambda与Papyrus native声明；C++前置及纯virtual声明的调用契约另在源码阅读中核查。source_reviewed 不等于调用链闭环或实机验证。', '',
              '| 文件 | 已提取 | 已读源码 | 待审 | 解析诊断 |', '| --- | ---: | ---: | ---: | ---: |']
    for file in files:
        members = [row for row in records if row['path'] == file['path']]
        reviewed = sum(row['status'] == 'source_reviewed' for row in members)
        pending = sum(row['status'] == 'pending' for row in members)
        report.append(f'| {file["path"]} | {len(members)} | {reviewed} | {pending} | {len(file["parse_errors"])} |')
    (OUT / 'status.md').write_text('\n'.join(report) + '\n')
    print(json.dumps({'files': len(files), 'lines': sum(x['lines'] for x in files), 'functions': len(records),
                      'status': dict(counts), 'parse_error_files': [x['path'] for x in files if x['parse_errors']], 'reconciled_parse_files': reconciled}, ensure_ascii=False))


if __name__ == '__main__':
    main()
