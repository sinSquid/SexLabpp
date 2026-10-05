"""Whole-scope structural and native wiring checks, not a manual review certificate."""
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from build_inventory import inventory
from verify_scope import main as scope_check

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PATTERNS = {
    'queued_tasks': r'\bAddTask\s*\(',
    'detached_threads': r'\.detach\s*\(',
    'file_writes': r'\b(?:Submit|SaveToFile|write_file_json|ofstream|WriteRecordData)\s*\(',
    'direct_indices': r'\.(?:front|back|at)\s*\(',
    'numeric_conversions': r'\b(?:static_cast|stoi|stoul|stof|from_chars)\b',
    'unbounded_loop_syntax': r'while\s*\(true\)|for\s*\(\s*;\s*;\s*\)',
    'script_waits': r'\b(?:Wait|WaitMenuMode|RegisterForSingleUpdate|RegisterForSingleUpdateGameTime)\s*\(',
}


def clean_script(text):
    text = re.sub(r';/.*?/;', lambda m: '\n' * m[0].count('\n'), text, flags=re.S)
    return re.sub(r';[^\n]*', '', text)


def wiring():
    registered, declared = {}, {}
    for path in sorted((ROOT/'src').rglob('*.h')):
        text = path.read_text()
        for m in re.finditer(r'REGISTERFUNC\(\s*(\w+)\s*,\s*"([^"]+)"', text):
            registered[(m[2].lower(), m[1].lower())] = path
    for path in sorted((ROOT/'dist/Source/Scripts').glob('*.psc')):
        text = clean_script(path.read_text())
        for m in re.finditer(r'^\s*(?:\w+(?:\[\])?\s+)?function\s+(\w+)\(([^\n]*)\)\s*([^\n]*\bnative\b[^\n]*)', text, re.I|re.M):
            declared[(path.stem.lower(), m[1].lower())] = (path, m[2], bool(re.search(r'\bglobal\b', m[3], re.I)))
    mismatches, unsupported = [], []
    for key in sorted(registered.keys() & declared.keys()):
        text = re.sub(r'//[^\n]*', '', registered[key].read_text())
        m = re.search(r'\b'+re.escape(key[1])+r'\s*\(([^()]*)\)\s*(?:;|\{)', text, re.I|re.S)
        if not m:
            unsupported.append(list(key)); continue
        args = re.sub(r'\b(?:QUESTARGS|ALIASARGS|STATICARGS)\s*,?', '', m[1].strip())
        parts, depth, start = [], 0, 0
        for i,c in enumerate(args):
            depth += (c=='<') - (c=='>')
            if c==',' and depth==0:
                parts.append(args[start:i]); start=i+1
        parts.append(args[start:])
        parts = [p for p in parts if p.strip() and not re.search(r'\b(?:VM|StackID|StaticFunctionTag)\b',p)]
        _, script_args, global_function = declared[key]
        if not global_function and parts and re.search(r'\b(?:TESQuest|BGSRefAlias)\b',parts[0]):
            parts.pop(0)
        script_count = len([p for p in script_args.split(',') if p.strip()])
        if len(parts)!=script_count:
            mismatches.append({'script':key[0], 'function':key[1], 'cpp_count':len(parts), 'psc_count':script_count})
    return {'registered':len(registered), 'declared':len(declared),
            'declared_without_registration':[list(k) for k in sorted(declared.keys()-registered.keys())],
            'registered_without_declaration':[list(k) for k in sorted(registered.keys()-declared.keys())],
            'arity_checked':len(registered.keys() & declared.keys())-len(unsupported),
            'arity_mismatches':mismatches, 'unsupported_signatures':unsupported,
            'limitation':'Name and argument-count checks only; does not validate full type mapping, VM or SDK ABI.'}


def main():
    scope_check()
    files, functions, excluded = inventory()
    scan = []
    for record in files:
        text = (ROOT/record['path']).read_text(encoding='utf-8-sig')
        hits = {}
        for rule, pattern in PATTERNS.items():
            matches = list(re.finditer(pattern, text, re.I if record['path'].endswith('.psc') else 0))
            if matches:
                hits[rule] = sorted({text.count('\n',0,m.start())+1 for m in matches})
        scan.append({'path':record['path'], 'sha256':record['sha256'], 'lines':record['lines'],
                     'structural_scan_complete':True, 'risk_surface_locations':hits,
                     'parser_diagnostics':record['parse_errors'], 'manual_review_implied':False})
    native = wiring()
    report = {'baseline':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'production_files_scanned':len(scan), 'production_lines':sum(x['lines'] for x in scan),
              'extracted_entries':len(functions), 'files':scan, 'native_wiring':native,
              'limits':['Pattern locations are candidates, not confirmed errors.',
                        'This pass does not claim a fresh manual reread of every function.',
                        'Portable/source checks do not compile the Windows DLL or Papyrus PEX.']}
    (OUT/'round-full-scan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'production_files_scanned':len(scan), 'native_wiring':native},ensure_ascii=False))
    if any(native[k] for k in ('declared_without_registration','registered_without_declaration','arity_mismatches','unsupported_signatures')):
        raise SystemExit(1)

if __name__=='__main__':
    main()
