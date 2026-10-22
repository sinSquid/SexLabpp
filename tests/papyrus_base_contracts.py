"""Evaluate production tag predicates and check hook guards (not Papyrus VM execution)."""
import re
from fork_review_regressions import ROOT

base = (ROOT / 'dist/Source/Scripts/sslBaseObject.psc').read_text()
hook = (ROOT / 'dist/Source/Scripts/SexLabThreadHook.psc').read_text()

def body(source, name):
    return re.search(r'(?im)^.*?\bFunction\s+' + name + r'\([^\n]*\)\s*\n(.*?)^\s*EndFunction',
                     source, re.S | re.M | re.I).group(1)

class Tags(list):
    def Find(self, item):
        return self.index(item) if item in self else -1

def predicate(name, tag, values):
    block = body(base, name)
    expression = re.search(r'(?im)^\s*(?:return|if)\s+(.+)$', block).group(1)
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    return bool(eval(expression, {'__builtins__': {}}, {'Tag': tag, 'Tags': Tags(values)}))

for values in ([], ['a'], ['a', 'b'], ['']):
    for tag in ('', 'a', 'b', 'missing'):
        present = bool(tag) and tag in values
        assert predicate('HasTag', tag, values) == present
        assert predicate('RemoveTag', tag, values) == present
        assert predicate('AddTag', tag, values) == (bool(tag) and tag not in values)
assert body(base, '_SetEnabled').strip() == '_enabled = aSet'
for name in ('IsLocked', 'SetLocked'):
    block = body(hook, name)
    assert block.index('If (!akThread)') < block.index('akThread.GetThreadID()')
    assert block.index('If (id < 0 || id >= _m.Length)') < block.index('_m[id]')
    guard = block[block.index('If (id < 0'):block.index('_m[id]')]
    assert re.search(r'(?im)^\s*return\b', guard)
print('PASS: production base-object predicates/setter and hook guard contracts; not a VM test')
