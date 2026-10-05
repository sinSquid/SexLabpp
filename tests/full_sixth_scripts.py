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
    text = re.sub(r'\(\((.*?)\) as int\)', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\((.*?)\) as int', r'int(\1)', text, flags=re.I)
    text = re.sub(r'\bnew\s+(\w+)\[(\d+)\]',
                  lambda m: f'Array([{dict(int="0", float="0.0", bool="False", string="\"\"").get(m[1].lower(), "None")}] * {m[2]})',
                  text, flags=re.I)
    text = re.sub(r'\s+as\s+(?:sslBaseExpression|sslBaseAnimation|sslBaseVoice)\b', '', text, flags=re.I)
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
        declaration = re.match(r'^(?:int|float|bool|string|Actor|ObjectReference|Form|sslBaseAnimation|sslBaseExpression|sslBaseVoice|sslActorAlias|sslThreadModel|Alias)(\[\])?\s+(\w+)(.*)$', line, flags=re.I)
        if declaration:
            line = declaration[2] + (declaration[3] or (' = Array()' if declaration[1] else ' = 0'))
        lines.append('    ' * indent + expression(line))
    assert indent == 1, name
    namespace = dict(environment, Array=Array, _length=len)
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


def test_merge():
    increase = helper('sslUtility', 'IncreaseAnimation', 'by, Array', {
        'AnimationArray': lambda size: globals()['Array']([None] * size)})
    merge = helper('sslUtility', 'MergeAnimationLists', 'List1, List2', {
        'sslUtility': SimpleNamespace(IncreaseAnimation=increase)})
    cases = [([], [], []), (['A'], ['B'], ['A', 'B']),
             ([], ['A', 'A', 'B'], ['A', 'B']),
             (['A', 'B'], ['B', 'C', 'C', 'D'], ['A', 'B', 'C', 'D']),
             (['A', 'A'], ['A', 'B'], ['A', 'A', 'B']),
             (['A', None], [None, 'B'], ['A', None, 'B']),
             (list(range(127)), [126, 127, 128], list(range(128))),
             (list(range(128)), [128, 129], list(range(128))),
             ([], list(range(200)), list(range(128)))]
    for first, second, expected in cases:
        left, right = Array(first), Array(second)
        assert merge(left, right) == expected, (first, second, expected)
        assert left == first and right == second, 'must not modify the inputs'


def test_trim():
    slices = []

    def substring(text, start, length=0):
        slices.append((start, length))
        return text[start:] if length == 0 else text[start:start + length]

    trim = helper('sslUtility', 'Trim', 'var', {'StringUtil': SimpleNamespace(
        GetLength=len, GetNthChar=lambda text, index: text[index] if 0 <= index < len(text) else '',
        SubString=substring)})
    for text in ('', 'abc', 'abc ', ' abc', '  abc  ', ' ', '   ', ' a b ', '\tabc\t',
                 ' ' * 5000 + 'content' + ' ' * 5000, ' ' * 10000):
        slices.clear()
        assert trim(text) == text.strip(' '), repr(text)
        assert len(slices) <= 1, 'trimming must not repeatedly copy the string'


def test_phase():
    profiles = [[10, 20], [30, 40]]

    def get_values(registry, female, level):
        values = profiles[int(female)]
        return values[level] if 0 <= level < len(values) else 0

    def set_values(registry, female, level, preset):
        if 0 <= level <= 1:
            profiles[int(female)][level] = preset

    env = {'Registry': 'profile', 'Female': 1, 'GetNthValues': get_values, 'SetValues': set_values}
    get_phase = helper('sslBaseExpression', 'GenderPhase', 'Phase, Gender', env)
    set_phase = helper('sslBaseExpression', 'SetPhase', 'Phase, Gender, Preset', env)
    assert get_phase(1, 0) == 10
    assert get_phase(2, 1) == 40
    set_phase(1, 0, 55)
    assert profiles == [[55, 20], [30, 40]]
    set_phase(2, -1, 66)
    assert profiles == [[55, 66], [30, 66]]
    set_phase(0, 0, 99)
    assert profiles == [[55, 66], [30, 66]]
    assert get_phase(0, 0) == 0


def test_lips():
    calls = []
    smooth = helper('sslExpressionUtil', 'SmoothSetPhoneme', 'act, id, str_dest, modifier=1.0', {
        'PapyrusUtil': SimpleNamespace(ClampInt=lambda value, low, high: min(max(value, low), high)),
        'MfgConsoleFuncExt': SimpleNamespace(SetPhoneme=lambda *args: calls.append(args))})
    restore = [line.strip() for line in body('sslBaseVoice', 'MoveLipsEx').splitlines()
               if 'sslExpressionUtil.SmoothSetPhoneme' in line][-1]
    for phoneme, saved in ((1, 0), (7, 0.35), (15, 1)):
        eval(expression(restore), {'sslExpressionUtil': SimpleNamespace(SmoothSetPhoneme=smooth),
                                  'ActorRef': 'actor', 'Phoneme': phoneme, 'SavedP': saved})
        assert calls[-1] == ('actor', phoneme, int(saved * 100), 1), calls[-1]


def test_stat_float():
    calls = []
    setter = helper('sslActorStats', 'SetFloat', 'ActorRef, Stat, Value', {
        'SkillNames': lambda: Array(['Vaginal', 'Anal']),
        'SetLegacyStatistic': lambda *args: calls.append(('legacy', *args)),
        'SetStat': lambda *args: calls.append(('custom', *args))})
    setter('actor', 'Vaginal', 12.5)
    setter('actor', 'Custom', -2.25)
    assert calls == [('legacy', 'actor', 0, 12.5), ('custom', 'actor', 'Custom', -2.25)]


def test_tag_replacement():
    query = helper('sslAnimationSlots', 'GetByDefaultTags',
                   'Males, Females, IsAggressive, UsingBed, RestrictAggressive, Tags, TagsSuppressed, RequireAll', {
        'SexLabUtil': SimpleNamespace(MergeSplitTags=lambda tags, *args: Array(tags)),
        'PapyrusUtil': SimpleNamespace(PushString=lambda values, item: Array([*values, item]),
                                      ClearEmpty=lambda values: Array(value for value in values if value)),
        'AsBaseAnimation': lambda values: values,
        'GetByTypeImpl': lambda count, males, females, tags: tags,
        'GetByType': lambda count: Array()})
    assert query(1, 1, False, True, True, ['~Furniture', '~Standing', 'Other'], '', True) == [
        '-Furniture', '-Standing', 'Other', '-Forced']
    assert query(1, 1, False, False, True, ['~BedOnly', 'Other'], '', True) == ['-BedOnly', 'Other', '-Forced']


if __name__ == '__main__':
    failures = []
    for test in (test_merge, test_trim, test_phase, test_lips, test_stat_float, test_tag_replacement):
        try:
            test()
            print(f'PASS: {test.__name__} (translated production script, API stand-ins)')
        except Exception as error:
            failures.append(test.__name__)
            print(f'FAIL: {test.__name__}: {type(error).__name__}: {error}')
    if failures:
        raise SystemExit(f'Failed: {", ".join(failures)}')
    print('PASS: script regressions; Papyrus compilation and game runtime were not tested')
