"""Execute a limited translation of production Papyrus helpers with API stand-ins.

These tests check script arithmetic/control flow and argument wiring. They do not
compile Papyrus or exercise its VM, scheduling, MFG plugin or game object ABI.
REVIEW_BASE=HEAD runs the same cases against the committed production sources.
"""
import os
import ast
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    path = f'dist/Source/Scripts/{name}.psc'
    if os.environ.get('REVIEW_BASE'):
        return subprocess.check_output(
            ['git', 'show', f'{os.environ["REVIEW_BASE"]}:{path}'], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


def body(script, name):
    match = re.search(r'\bfunction\s+' + re.escape(name) + r'\([^\n]*\)[ \t]*[^\n]*\n(.*?)\bendfunction\b',
                      source(script), flags=re.I | re.S)
    assert match, (script, name)
    return match.group(1)


class Array(list):
    def Find(self, value, start=0):
        try:
            return self.index(value, start)
        except ValueError:
            return -1

    def __setitem__(self, index, value):
        # Papyrus negative indices must not silently acquire Python semantics.
        assert 0 <= index < len(self), (index, len(self))
        super().__setitem__(index, value)


def expression(text):
    text = re.sub(r'\b([A-Za-z_]\w*)\.Length\b', r'_length(\1)', text, flags=re.I)
    text = re.sub(r'\((SavedP \* 100)\) as int', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\((str_dest \* modifier)\) as Int', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\b([A-Za-z_]\w*\[[^][\n]+\])\s+as\s+(int|float)\b',
                  lambda m: f'{m[2].lower()}({m[1]})', text, flags=re.I)
    text = re.sub(r'\(([^(),\n]+)\)\s+as\s+(int|float)\b',
                  lambda m: f'{m[2].lower()}({m[1]})', text, flags=re.I)
    text = re.sub(r'\(\((.*?)\) as int\)', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\((.*?)\) as int', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\bnew\s+(\w+)\[(\d+)\]',
                  lambda m: f'_Array([{dict(int="0", float="0.0", bool="False", string="\"\"").get(m[1].lower(), "None")}] * {m[2]})',
                  text, flags=re.I)
    text = re.sub(r'\s+as\s+(?:sslBaseExpression|sslBaseAnimation|sslBaseVoice)\b', '', text, flags=re.I)
    text = re.sub(r'\b([A-Za-z_]\w*)\s+as\s+(Weapon|Spell)\b',
                  lambda m: f'_cast_{m[2].lower()}({m[1]})', text, flags=re.I)
    text = re.sub(r'\b([A-Za-z_]\w*)\s+as\s+(int|float)\b', lambda m:f'{m[2].lower()}({m[1]})', text, flags=re.I)
    text = text.replace('&&', ' and ').replace('||', ' or ')
    text = re.sub(r'!(?!=)', 'not ', text)
    for token, replacement in (('true', 'True'), ('false', 'False'), ('none', 'None')):
        text = re.sub(r'\b' + token + r'\b', replacement, text, flags=re.I)
    return text


def strip_comment(line):
    quoted = escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == ';' and not quoted:
            return line[:index]
    return line


def helper(script, name, arguments, environment, state_names=()):
    """Translate only the statement subset present in the selected helpers."""
    lines = [f'def selected({arguments}):']
    if state_names:
        lines.append('    global ' + ', '.join(state_names))
    indent = 1
    for original in body(script, name).splitlines():
        line = strip_comment(original).strip()
        if not line:
            continue
        if re.fullmatch(r'end(if|while)', line, flags=re.I):
            indent -= 1
            continue
        branch = re.match(r'^(elseif|else)\b(.*)', line, flags=re.I)
        if branch:
            indent -= 1
            suffix = expression(branch[2]).strip()
            lines.append('    ' * indent + ('elif ' + suffix if suffix else 'else') + ':')
            indent += 1
            continue
        start = re.match(r'^(if|while)\b(.*)', line, flags=re.I)
        if start:
            lines.append('    ' * indent + start[1].lower() + ' ' + expression(start[2]).strip() + ':')
            indent += 1
            continue
        declaration = re.match(r'^(?:int|float|bool|string|Actor|ObjectReference|Form|Weapon|Spell|sslBaseAnimation|sslBaseExpression|sslBaseVoice|sslActorAlias|sslThreadModel|Alias)(\[\])?\s+(\w+)(.*)$', line, flags=re.I)
        if declaration:
            line = declaration[2] + (declaration[3] or (' = Array()' if declaration[1] else ' = 0'))
        lines.append('    ' * indent + expression(line))
    assert indent == 1, name
    namespace = dict(environment, Array=Array, _Array=Array, _length=len)
    # Papyrus concatenates strings with scalar values implicitly.
    class StringAddition(ast.NodeTransformer):
        def visit_BinOp(self, node):
            self.generic_visit(node)
            if isinstance(node.op, ast.Add):
                return ast.copy_location(ast.Call(func=ast.Name(id='_papyrus_add', ctx=ast.Load()),
                    args=[node.left, node.right], keywords=[]), node)
            return node
    namespace['_papyrus_add'] = lambda a,b: str(a)+str(b) if isinstance(a,str) or isinstance(b,str) else a+b
    tree = ast.fix_missing_locations(StringAddition().visit(ast.parse('\n'.join(lines))))
    exec(compile(tree, f'<{script}.{name} translated>', 'exec'), namespace)
    return namespace['selected']
