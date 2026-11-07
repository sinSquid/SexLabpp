"""Pure Python API regressions plus native source contracts; never compiles."""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--defeat-source', type=Path)
args = parser.parse_args()
old_args = sys.argv
try:
    sys.argv = ['scene_select_hotkey.py', '--papyrus-only']
    m = runpy.run_path(str(ROOT / 'tests/scene_select_hotkey.py'))
finally:
    sys.argv = old_args


def execute(code, env):
    env['Returned'] = m['Returned']
    try:
        exec(code, env)
    except m['Returned'] as result:
        return result.value


opened = m['translated_body'](m['controller'], 'OpenSceneSelection')
selected = m['translated_body'](m['controller'], 'SelectExternalSceneFromHUD')
for status, menu, controlled, available, expected in (
    (3, False, False, True, True), (3, False, False, False, False),
    (2, False, False, True, False), (4, False, False, True, False),
    (3, True, False, True, False), (3, False, True, True, True)):
    calls = []
    env = dict(GetStatus=lambda: status, STATUS_INSCENE=3,
               Utility=NS(IsInMenuMode=lambda: menu), _SceneHotkeysEnabled=controlled,
               _bFocusedSceneHUD=True, SceneSelectAutoClose=True,
               OpenSceneSelect=lambda: calls.append('existing'),
               OpenExternalSceneSelectImpl=lambda: calls.append('external') or available)
    assert execute(opened, env) == expected
    assert calls == ([] if status != 3 or menu else ['existing' if controlled else 'external'])

for outcome in ('applied', 'queued', 'ignored', 'rejected', 'stale', 'closed-during-reset', 'ending'):
    state = dict(active='old', queue='', ticket=12)
    calls = []
    def reset(scene):
        calls.append('reset')
        if outcome == 'applied': state['active'] = scene
        if outcome == 'queued': state['queue'] = scene
        if outcome == 'closed-during-reset':
            state['ticket'] += 1
            state['active'] = scene
        return outcome != 'rejected'
    def close(ticket):
        if ticket == state['ticket']:
            calls.append('close')
    env = dict(asSceneId='new', aiTicket=11 if outcome == 'stale' else 12,
        STATUS_INSCENE=3, GetStatus=lambda: 4 if outcome == 'ending' else 3,
        IsExternalSceneSelectCurrentImpl=lambda ticket: ticket == state['ticket'],
        GetActiveScene=lambda: state['active'], GetQueuedSceneReset=lambda: state['queue'],
        ResetScene=reset, CloseExternalSceneSelectImpl=close)
    execute(selected, env)
    assert ('close' in calls) == (outcome in ('applied', 'queued')), (outcome, calls)
    assert ('reset' in calls) == (outcome not in ('stale', 'ending'))


def function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


hud = (ROOT / 'src/Thread/Interface/SceneHUD.cpp').read_text(encoding='utf-8')
api = function(hud, 'bool SceneHUD::OpenExternalSceneSelect(')
repeat = function(api, 'if (_externalSceneSelect && GetForThread(a_quest))')
repeat = repeat[repeat.index('{') + 1:-1].replace('PanelId::kSceneSelect', '"scenes"')
repeat = re.sub(r'return\s+([^;]+);', lambda x: 'return ' + ' '.join(x[1].split()) + ';', repeat)
repeat = re.sub(r'if \((.*?)\)\s*((?:return|OpenPanel)[^;]*);',
                lambda x: 'If (' + x[1] + ')\n' + x[2] + '\nEndIf', repeat, flags=re.S)
repeat = m['translated_body']('bool Function RepeatOpen()\n' + repeat.replace(';', '') + '\nEndFunction', 'RepeatOpen')
for initial, closing in ((None, False), ('scenes', False), (None, True), ('scenes', True)):
    state = dict(panel=initial, opens=0)
    def open_panel(panel):
        state['opens'] += 1
        # The actual panel API toggles; a missing guard would collapse it.
        state['panel'] = None if state['panel'] == panel else panel
    env = dict(_externalCloseRequested=closing, IsPanelOpen=lambda panel: state['panel'] == panel,
        OpenPanel=open_panel, IsExternalSceneSelectCurrent=lambda quest, ticket: True,
        a_quest=object(), GetExternalSceneSelectTicket=lambda: 12)
    assert execute(repeat, env) == (not closing)
    assert execute(repeat, env) == (not closing)
    assert state['panel'] == (initial if closing else 'scenes')
    assert state['opens'] == (1 if initial is None and not closing else 0)
print('PASS: extracted native repeat-open branch expands a collapsed list, keeps an open list and rejects closing windows (Python execution only)')
assert api.index('if (IsActive() || _speedThread)') < api.index('Init(a_quest, false)')
assert 'script->currentState != "Animating"' in api
assert 'GetActiveScene()' in api and 'GetActiveStage()' in api
for forbidden in ('GetThreadControl', 'AutoAdvance', 'UpdateAnimatingActorMovement', 'ToggleFreeCamera'):
    assert forbidden not in api and forbidden not in m['controller'].split('bool Function OpenSceneSelection()')[1].split('EndFunction')[0]
init = function(hud, 'void SceneHUD::Init(')
assert 'if (a_bindSpeedControl)\n            SetSpeedControl(a_quest, true);' in init
render = function(hud, 'void SceneHUD::Render()')
assert render.index('IsExternalSceneSelectCurrent') < render.index('ShouldRender()')
cleanup = render[render.index('if (_externalCloseRequested)'):]
assert cleanup.index('PopStyleColor(5)') < cleanup.index('Destroy()')
assert cleanup.index('Destroy()') < cleanup.index('switch (_activePanel)')
close = function(hud, 'bool SceneHUD::CloseExternalSceneSelect(')
assert '_linkedThread != a_quest' in close and 'a_ticket != GetExternalSceneSelectTicket()' in close
thread = (ROOT / 'src/Thread/Thread.cpp').read_text(encoding='utf-8')
assert 'CloseExternalSceneSelect(a_linkedQst)' in function(thread, 'void Instance::DestroyInstance(')
normal_init = function(thread, 'void Instance::InitSceneHUDImpl()')
assert 'sceneHUD.IsExternalSceneSelect() ||' in normal_init
tabs = (ROOT / 'src/Thread/Interface/Elements/PseudoPanelStack.cpp').read_text(encoding='utf-8')
assert 'a_hud.RequestExternalSceneSelectClose();' in tabs
assert 'CloseExternalSceneSelect(' not in tabs # Never delete the component inside its own Render.
panel = (ROOT / 'src/Thread/Interface/Elements/SceneSelectPanel.cpp').read_text(encoding='utf-8')
assert re.search(r'"SelectExternalSceneFromHUD",\s*a_hud.GetCallback\(\), RE::BSFixedString\{ a_sceneId.c_str\(\) \}, a_hud.GetExternalSceneSelectTicket\(\)', panel)
bindings = (ROOT / 'src/Papyrus/sslThreadModel.h').read_text(encoding='utf-8')
model = (ROOT / 'dist/Source/Scripts/sslThreadModel.psc').read_text(encoding='utf-8')
for name, signature in (('OpenExternalSceneSelectImpl', ''), ('IsExternalSceneSelectCurrentImpl', 'int aiTicket'), ('CloseExternalSceneSelectImpl', 'int aiTicket')):
    assert f'bool Function {name}({signature}) native' in model
    assert f'REGISTERFUNC({name}, "sslThreadModel", false)' in bindings

# Original Alt and shortcut handlers retain their exact bodies.
before = subprocess.check_output(['git', 'show', 'e0c0f7c9399b34559d8b812826a5d8539bb41795:dist/Source/Scripts/sslThreadController.psc'], cwd=ROOT).decode('utf-8')
for name in ('OpenSceneSelect', 'ToggleFocusSceneHUD', 'ToggleFocusSceneHUDForRevision', 'SelectSceneFromHUD'):
    assert m['translated_body'](before, name).co_code == m['translated_body'](m['controller'], name).co_code
    pattern = r'(?ims)^Function '+name+r'\([^\n]*\).*?^EndFunction'
    assert re.search(pattern, before)[0] == re.search(pattern, m['controller'])[0]

if args.defeat_source:
    defeat = args.defeat_source.read_text(encoding='utf-8-sig')
    # Erase only a type declaration unsupported by the small PSC translator.
    test_source = defeat.replace('SexLabThread ApiThread', 'sslThreadController ApiThread')
    # Papyrus implicitly converts the integer when concatenating a label.
    test_source = test_source.replace('"Stage " + (ApiIndex + 1)', '"Stage " + str(ApiIndex + 1)')
    code = m['translated_body'](test_source, 'SLController')
    for stages in (False, True):
        calls = []
        api_thread = NS(GetStatus=lambda: 3, GetActiveScene=lambda: 'scene',
            GetActiveStage=lambda: 's1', OpenSceneSelection=lambda: calls.append('pplus') or True,
            SkipTo=lambda stage: calls.append(('stage', stage)))
        ui = NS(InitMenu=lambda *a: calls.append('list'), SetMenuPropertyInt=lambda *a: None,
            SetMenuPropertyIndexString=lambda *a: None, SetMenuPropertyIndexInt=lambda *a: None,
            OpenMenu=lambda *a: None, GetMenuResultInt=lambda *a: 1)
        env = dict(Target=object(), SexLab=NS(GetThreadByActor=lambda actor: api_thread),
            Input=NS(IsKeyPressed=lambda key: stages), HotKeyInts=[11,42], UIExtensions=ui,
            SexLabRegistry=NS(GetAllStages=lambda scene: ['s1','s2']), DefeatConfig=NS(Log=lambda msg: None))
        execute(code, env)
        assert calls == (['list', ('stage','s2')] if stages else ['pplus']), calls
    print('PASS: actual Defeat Scene branch opens P+, modifier branch retains UIListMenu + SkipTo')
print('PASS: playing/API routing, accepted/queued/ignored/stale selection, native owner/cleanup/signatures source contracts; original Alt/Open bodies unchanged. Native not executed or compiled.')
