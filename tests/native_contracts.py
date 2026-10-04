"""Check native declaration/registration names; does not compile Papyrus bytecode."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
registrations=set()
for path in (ROOT/'src').rglob('*'):
 if path.suffix not in ('.h','.cpp'): continue
 source=path.read_text()
 for name,script in re.findall(r'REGISTERFUNC\(\s*(\w+)\s*,\s*"([^"]+)"',source):
  registrations.add((script.lower(),name.lower()))
missing=[];count=0
for path in (ROOT/'dist/Source/Scripts').glob('*.psc'):
 source=re.sub(r';/.*?/;','',path.read_text(),flags=re.S)
 source=re.sub(r';[^\n]*','',source)
 script=re.search(r'(?im)^\s*ScriptName\s+(\w+)',source)
 if not script:continue
 for name in re.findall(r'(?im)^\s*(?:\w+(?:\[\])?\s+)?Function\s+(\w+)\s*\([^)]*\)[^\n]*\bnative\b',source):
  count+=1
  if (script[1].lower(),name.lower()) not in registrations:missing.append(f'{script[1]}.{name}')
assert not missing, 'Unregistered native declarations: '+', '.join(missing)
print(f'PASS: {count} Papyrus native declarations matched to registrations')
