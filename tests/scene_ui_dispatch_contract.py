"""Verify native Return/Escape dispatch matches the public Papyrus ABI.

PEX parameter tables do not contain PSC default arguments; native callers must
not rely on the Papyrus compiler filling in an added optional parameter.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
psc = (ROOT / 'dist/Source/Scripts/sslThreadController.psc').read_text(encoding='utf-8')
panel = (ROOT / 'src/Thread/Interface/Elements/PseudoPanelStack.cpp').read_text(encoding='utf-8')
params = re.search(r'(?im)^Function ToggleFocusSceneHUD\(([^)]*)\)', psc)[1].split(',')
assert len(params) == 1, 'Return/Escape supplies one argument, but the public PSC method now requires a larger parameter table'
assert re.search(r'DispatchMethodCall\([^;]*"ToggleFocusSceneHUD",\s*a_hud.GetCallback\(\),\s*-1\)', panel)
wrapper = re.search(r'(?ims)^Function ToggleFocusSceneHUD\([^\n]*\)\s*(.*?)^EndFunction', psc)[1]
assert 'ToggleFocusSceneHUDForRevision(aiForceState, -1)' in wrapper
assert 'ToggleFocusSceneHUDForRevision(1, revision)' in psc
print('PASS: native Return/Escape keeps the one-argument public ABI; guarded shortcut uses a separate two-argument method')
