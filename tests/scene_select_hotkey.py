"""Run extracted HUD C++ and Papyrus control bodies with engine stand-ins.

This is not a Papyrus VM or in-game input-capture test.
"""
from pathlib import Path
from types import SimpleNamespace
import os
import re
import subprocess
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
controller = Path(os.environ.get('SCENE_CONTROLLER_SOURCE', ROOT / 'dist/Source/Scripts/sslThreadController.psc')).read_text(encoding='utf-8')
menu = (ROOT / 'dist/Source/Scripts/sslConfigMenu.psc').read_text(encoding='utf-8')
hud = (ROOT / 'src/Thread/Interface/SceneHUD.cpp').read_text(encoding='utf-8')
system = (ROOT / 'dist/Source/Scripts/sslSystemConfig.psc').read_text(encoding='utf-8')


def cpp_function(signature):
    start = hud.index(signature)
    brace = hud.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (hud[end] == '{') - (hud[end] == '}')
        end += 1
    return hud[start:end]


cpp = r'''
#include <cassert>
namespace RE { struct TESQuest {}; struct UI {
 bool paused = false;
 static UI* GetSingleton() { static UI ui; return &ui; }
 bool GameIsPaused() { return paused; }
}; }
struct Instance { static inline bool alive = true;
 static bool GetInstance(RE::TESQuest*) { return alive; }
};
enum class PanelId { kNone, kOther, kSceneSelect };
class SceneHUD { public:
 RE::TESQuest* _speedThread = nullptr;
 RE::TESQuest* linked = nullptr;
 bool _registered = true, _renderEnabled = true, _elements = false;
 bool _threadScript = false, _focused = false, initSucceeds = true;
 int initCount = 0, openCount = 0;
 PanelId panel = PanelId::kNone;
 bool IsActive() { return linked; }
 bool GetForThread(RE::TESQuest* q) { return q && q == linked; }
 bool ShouldRender() { return IsActive() && _renderEnabled && !RE::UI::GetSingleton()->paused; }
 bool IsPanelOpen(PanelId p) { return panel == p; }
 void Init(RE::TESQuest* q) { ++initCount; if (initSucceeds) { linked=q; _elements=_threadScript=true; } }
 void OpenPanel(PanelId p) { ++openCount; panel = panel == p ? PanelId::kNone : p; }
 bool PrepareSceneSelect(RE::TESQuest*);
 bool OpenSceneSelect(RE::TESQuest*);
};
'''
cpp += cpp_function('bool SceneHUD::PrepareSceneSelect(')
cpp += cpp_function('bool SceneHUD::OpenSceneSelect(')
cpp += r'''
int main() {
 RE::TESQuest q, other;
 SceneHUD h; h._speedThread=&q;
 assert(!h.PrepareSceneSelect(nullptr));
 assert(!h.PrepareSceneSelect(&other));
 h._registered=false; assert(!h.PrepareSceneSelect(&q)); h._registered=true;
 h.initSucceeds=false; assert(!h.PrepareSceneSelect(&q)); assert(!h._focused);
 h.initSucceeds=true; assert(h.PrepareSceneSelect(&q));
 const int inits=h.initCount;
 assert(h.PrepareSceneSelect(&q) && h.initCount==inits);
 assert(!h.OpenSceneSelect(&q));
 h._focused=true; h.panel=PanelId::kOther;
 assert(h.OpenSceneSelect(&q) && h.openCount==1);
 assert(h.OpenSceneSelect(&q) && h.openCount==1); // Must not toggle closed.
 h._speedThread=nullptr; assert(!h.OpenSceneSelect(&q));
 h._speedThread=&other; assert(!h.PrepareSceneSelect(&other));
 h._speedThread=&q; Instance::alive=false;
 assert(!h.PrepareSceneSelect(&q) && !h.OpenSceneSelect(&q)); Instance::alive=true;
 h._renderEnabled=false; assert(!h.PrepareSceneSelect(&q) && !h.OpenSceneSelect(&q));
 h._renderEnabled=true; RE::UI::GetSingleton()->paused=true;
 assert(!h.PrepareSceneSelect(&q) && !h.OpenSceneSelect(&q));
}
'''
if '--papyrus-only' not in sys.argv:
    with tempfile.TemporaryDirectory(prefix='scene-select-') as directory:
        source, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
        source.write_text(cpp, encoding='utf-8')
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


class Returned(Exception):
    def __init__(self, value=None): self.value = value


def translated_body(source, name):
    match = re.search(r'(?im)^\s*(?:(?:bool|string|int) )?(?:Function|Event) ' + name + r'\([^\n]*\)\s*\n(.*?)^\s*End(?:Function|Event)', source, re.S)
    assert match, name
    result, indent = [], 0
    for raw in match[1].splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low in ('endif', 'endwhile'):
            indent -= 1
            continue
        declaration = re.fullmatch(r'(?:bool|int|string)(?:\[\])?\s+(\w+)', line, re.I)
        if declaration:
            line = declaration[1] + ' = None'
        line = re.sub(r'^(?:bool|int|string|sslThreadController)(?:\[\])?\s+', '', line, flags=re.I)
        line = re.sub(r'\bnew int\[(\d+)\]', r'([-1] * \1)', line, flags=re.I)
        line = re.sub(r'\b([\w]+)\.Length\b', r'len(\1)', line)
        line = re.sub(r'\b(\w+)\.Find\((\w+)\)', r'find(\1, \2)', line)
        line = line.replace('&&', ' and ').replace('||', ' or ')
        line = re.sub(r'!(?!=)', 'not ', line)
        line = re.sub(r'\btrue\b', 'True', line, flags=re.I)
        line = re.sub(r'\bfalse\b', 'False', line, flags=re.I)
        if low.startswith('elseif '):
            indent -= 1
            line = 'elif ' + line[7:] + ':'
        elif low == 'else':
            indent -= 1
            line = 'else:'
        elif low.startswith('if ') or low.startswith('if('):
            line = 'if ' + line[2:].strip() + ':'
        elif low.startswith('while '):
            line = 'while ' + line[6:] + ':'
        elif low == 'return' or low.startswith('return '):
            line = 'raise Returned(' + line[6:].strip() + ')'
        result.append('    ' * indent + line)
        if line.endswith(':'):
            indent += 1
    assert indent == 0
    return compile('\n'.join(result), name, 'exec')


bodies = {name: translated_body(controller, name) for name in (
    'InitHotkeys', 'RegisterHotkeys', 'UnregisterHotkeys', 'RefreshSceneSelectHotkey', 'OpenSceneSelect', 'ToggleFocusSceneHUD', 'ToggleFocusSceneHUDForRevision')}
bodies['OnKeyMapChangeST'] = translated_body(menu, 'OnKeyMapChangeST')
bodies['IsOtherThreadHotkey'] = translated_body(controller, 'IsOtherThreadHotkey')
for name in ('HandleSceneSelectMainKey', 'HandleThreadHotkey'):
    bodies[name] = translated_body(controller, name)
for name in ('HasSceneSelectKeyConflict', 'IsSceneSelectShortcut', 'IsSceneSelectModifier', 'IsSceneSelectMainKey', 'HandleGlobalHotkey', 'IsGlobalHotkey'):
    bodies[name] = translated_body(system, name)
bodies['PauseTimer'] = translated_body((ROOT / 'dist/Source/Scripts/sslThreadModel.psc').read_text(encoding='utf-8'), 'PauseTimer')


def fixture():
    calls, registered, settings = [], set(), {'iOpenSceneSelect': -1}
    thread_keys, config_keys = set(), set()
    def register(owner, key):
        owner.add(key)
        registered.add(key)
    def unregister(owner, key):
        owner.discard(key)
        if key not in thread_keys and key not in config_keys:
            registered.discard(key)
    e = dict(Returned=Returned, find=lambda items, value: items.index(value) if value in items else -1,
             _SceneHotkeysEnabled=True, _OpeningSceneSelect=False,
             _SceneSelectRevision=1, SceneSelectUIRevision=0, SceneSelectAutoClose=False,
             _bOpenedSceneHUD=False, _bFocusedSceneHUD=False,
             _bOpenedSceneGraph=False, ElementUI_GameHUD=True, STATUS_INSCENE=3,
             HasPlayer=True, Hotkeys=[], GetStatus=lambda: 3, GetAdjustPos=lambda: None,
             RegisterForKey=lambda key: register(thread_keys, key),
             UnregisterForKey=lambda key: unregister(thread_keys, key),
             threadKeys=thread_keys, configKeys=config_keys,
             Utility=SimpleNamespace(IsInMenuMode=lambda: False),
             RefreshPropertiesSceneHUD=lambda mode: calls.append('properties'),
             PrepareSceneSelectImpl=lambda: True, OpenSceneSelectImpl=lambda: True,
             SexLabUtil=SimpleNamespace(HideElementsGameHUD=lambda v: calls.append(('hide', v))))
    for name, number in re.findall(r'int Property (k\w+)\s*=\s*(\d+)', controller):
        e[name] = int(number)
    config = SimpleNamespace(**dict(ToggleSceneHUD=53, FocusSceneHUD=184, ToggleSceneGraph=156,
        AdvanceAnimation=57, EndAnimation=207, GameRaiseEnjKey=30, GameHoldbackKey=31,
        ChangeAnimation=24, MoveScene=37, TargetActor=49, GameEnabled=True))
    e['Config'] = config
    e['sslSystemConfig'] = SimpleNamespace(GetSettingInt=lambda key: settings.get(key, -1),
        SetSettingInt=lambda key, value: settings.__setitem__(key, value))

    def run(name):
        try:
            exec(bodies[name], e)
        except Returned as result:
            return result.value

    def evaluate(name, **params):
        scope = dict(e, **params)
        try:
            exec(bodies[name], scope)
        except Returned as result:
            return result.value

    for name in bodies:
        e[name] = lambda name=name: run(name)
    e['GetSettingInt'] = lambda key: settings.get(key, -1)
    e['Input'] = SimpleNamespace(IsKeyPressed=lambda key: key in e.get('pressedKeys', set()))
    e['IsOtherThreadHotkey'] = lambda key: evaluate('IsOtherThreadHotkey', aiKey=key)
    config.HasSceneSelectKeyConflict = lambda setting, key: evaluate('HasSceneSelectKeyConflict', changedSetting=setting, newKey=key)
    config.IsSceneSelectShortcut = lambda key: evaluate('IsSceneSelectShortcut', keyCode=key)
    config.IsSceneSelectModifier = lambda key: evaluate('IsSceneSelectModifier', keyCode=key)
    config.IsSceneSelectMainKey = lambda key: evaluate('IsSceneSelectMainKey', keyCode=key)
    config.HandleGlobalHotkey = lambda key: evaluate('HandleGlobalHotkey', keyCode=key)
    config.IsGlobalHotkey = lambda key: evaluate('IsGlobalHotkey', keyCode=key)
    config.RegisterForKey = lambda key: register(config_keys, key)
    config.UnregisterForKey = lambda key: unregister(config_keys, key)
    e.update(ToggleFreeCamera=81, TargetActor=49, ToggleThreadControl=21, _ActiveControl=False)

    e['SetFocusSceneHUDImpl'] = lambda value: e.__setitem__('nativeFocused', value)
    e['SetFixedLengthTimerPaused'] = lambda value: e.__setitem__('timerPaused', value)
    def pause(value):
        e['abEnable'] = value
        run('PauseTimer')
    e['PauseTimer'] = pause
    e['EnjoymentPaused'] = False

    def guarded_focus(value, revision):
        calls.append(('focus', value))
        e['aiForceState'], e['aiExpectedRevision'] = value, revision
        run('ToggleFocusSceneHUDForRevision')

    def focus(value):
        e['aiForceState'] = value
        run('ToggleFocusSceneHUD')

    def graph(value):
        calls.append(('graph', value))
        e['_bOpenedSceneGraph'] = False

    e['ToggleFocusSceneHUD'], e['ToggleVisibilitySceneGraph'] = focus, graph
    e['ToggleFocusSceneHUDForRevision'] = guarded_focus
    e.update(StringUtil=SimpleNamespace(Split=lambda s, sep: s.split(sep)),
             GetState=lambda: 'iOpenSceneSelect', conflictControl='', conflictName='',
             ShowMessage=lambda *args: calls.append(('message', args)) or True,
             SetKeyMapOptionValueST=lambda value: calls.append(('value', value)))
    config.GetThreadControlled = lambda: SimpleNamespace(RefreshSceneSelectHotkey=e['RefreshSceneSelectHotkey'])
    return e, calls, registered, settings


# Execute actual control bodies, including MCM -> active-thread refresh.
e, calls, registered, settings = fixture()
e['RegisterHotkeys']()
assert -1 not in registered and len(e['Hotkeys']) == 11
for key in (34, 35, 1):
    e['newKeyCode'] = key
    e['OnKeyMapChangeST']()
    expected = -1 if key == 1 else key
    assert settings['iOpenSceneSelect'] == expected
    assert (34 in registered) == (expected == 34)
    assert (35 in registered) == (expected == 35)
assert 184 in registered and 53 in registered
for key in (203, 205, 42, 54, 184):
    settings['iFocusSceneHUD'] = 184
    e['newKeyCode'] = key
    e['OnKeyMapChangeST']()
    assert settings['iOpenSceneSelect'] == -1
settings['iOpenSceneSelect'] = 34
e['GetState'] = lambda: 'M_S_iFocusSceneHUD'
e['newKeyCode'] = 34
e['OnKeyMapChangeST']()
assert settings['iFocusSceneHUD'] == 184
e['_SceneHotkeysEnabled'] = False
before = registered.copy()
e['RefreshSceneSelectHotkey']()
assert registered == before

for field, value in (('_SceneHotkeysEnabled', False), ('_OpeningSceneSelect', True),
                     ('GetStatus', lambda: 0), ('Utility', SimpleNamespace(IsInMenuMode=lambda: True))):
    e, calls, _, _ = fixture()
    e[field] = value
    e['OpenSceneSelect']()
    assert not calls

e, calls, _, _ = fixture()
e['PrepareSceneSelectImpl'] = lambda: False
e['OpenSceneSelect']()
assert not e['_bOpenedSceneHUD'] and not e['_bFocusedSceneHUD'] and not e['_OpeningSceneSelect']
assert not any(isinstance(c, tuple) and c[0] in ('focus', 'hide') for c in calls)

e, calls, _, _ = fixture()
e['_bOpenedSceneGraph'] = True
e['OpenSceneSelect']()
assert e['_bOpenedSceneHUD'] and e['_bFocusedSceneHUD'] and not e['_bOpenedSceneGraph']
assert calls.index(('graph', -1)) < calls.index(('focus', 1))
e['OpenSceneSelectImpl'] = lambda: False
e['_bFocusedSceneHUD'] = False
e['OpenSceneSelect']()
assert not e['_bFocusedSceneHUD'] and calls[-1] == ('focus', -1)

e, calls, _, _ = fixture()
def end_during_prepare():
    e['_SceneHotkeysEnabled'] = False
    e['_SceneSelectRevision'] += 1
    e['_OpeningSceneSelect'] = False
    return True
e['PrepareSceneSelectImpl'] = end_during_prepare
e['OpenSceneSelect']()
assert not e['_bOpenedSceneHUD'] and not e['_bFocusedSceneHUD']

e, calls, _, _ = fixture()
e['_bFocusedSceneHUD'] = True
e['_bOpenedSceneHUD'] = True
e['OpenSceneSelectImpl'] = lambda: False
e['OpenSceneSelect']()
assert e['_bFocusedSceneHUD'] and ('focus', -1) not in calls

e, calls, _, _ = fixture()
def end_during_open():
    e['_SceneSelectRevision'] += 1
    e['_SceneHotkeysEnabled'] = False
    e['_OpeningSceneSelect'] = False
    e['_bFocusedSceneHUD'] = False
    return False
e['OpenSceneSelectImpl'] = end_during_open
e['OpenSceneSelect']()
assert not e['_bFocusedSceneHUD'] and not e['_OpeningSceneSelect']
# The stale stack must not unpause/refocus a subsequent control session.
assert ('focus', -1) not in calls


def release_control(e, registered):
    """Model the completed release; callers inject it at native call boundaries."""
    e['_SceneSelectRevision'] += 1
    e['_SceneHotkeysEnabled'] = False
    e['_OpeningSceneSelect'] = False
    e['_bOpenedSceneHUD'] = False
    e['_bFocusedSceneHUD'] = False
    e['EnjoymentPaused'] = False
    e['timerPaused'] = False
    e['_TimerPaused'] = False
    e['nativeFocused'] = False
    registered.clear()
    e['threadKeys'].clear()
    e['configKeys'].clear()


# Execute the actual focus body; release before/after its native effect completes.
e, calls, registered, settings = fixture()
e['_bOpenedSceneHUD'] = True
e['_SceneHotkeysEnabled'] = False
e['ToggleFocusSceneHUD'](1)
assert e['_bFocusedSceneHUD'] and e['EnjoymentPaused'] and e['timerPaused']
e['ToggleFocusSceneHUD'](-1)
assert not e['_bFocusedSceneHUD'] and not e['EnjoymentPaused'] and not e['timerPaused']
# Existing Alt/UI callers omit the revision and retain their original behavior.

for boundary in ('SetFocusSceneHUDImpl', 'SetFixedLengthTimerPaused'):
    for release_first in (False, True):
        e, calls, registered, settings = fixture()
        native = e[boundary]

        def interrupted(value, native=native, release_first=release_first):
            if value:
                if release_first:
                    release_control(e, registered)
                    native(value)
                else:
                    native(value)
                    release_control(e, registered)
                e['OpenSceneSelectImpl'] = lambda: False
            else:
                native(value)

        e[boundary] = interrupted
        e['OpenSceneSelect']()
        assert not e['_SceneHotkeysEnabled']
        assert not e['_bFocusedSceneHUD'] and not e['EnjoymentPaused']
        assert not e['timerPaused'] and not e['nativeFocused'], boundary

# Releasing and reacquiring control inside the native focus call must not let
# the old request overwrite the new session's unfocused state.
e, calls, registered, settings = fixture()
def reacquire_during_focus(value):
    release_control(e, registered)
    e['_SceneSelectRevision'] += 1
    e['_SceneHotkeysEnabled'] = True
    e['_bOpenedSceneHUD'] = True
    e['OpenSceneSelectImpl'] = lambda: False
e['SetFocusSceneHUDImpl'] = reacquire_during_focus
e['OpenSceneSelect']()
assert not e['_bFocusedSceneHUD'] and not e['EnjoymentPaused'] and not e['timerPaused']

# A late fixed-timer native call must match the new session's UI pause state.
for focused in (False, True):
    e, calls, registered, settings = fixture()
    fired = [False]
    def reacquire_during_pause(value):
        if not fired[0]:
            fired[0] = True
            release_control(e, registered)
            e['_SceneSelectRevision'] += 1
            e['_SceneHotkeysEnabled'] = True
            e['_bOpenedSceneHUD'] = True
            e['_bFocusedSceneHUD'] = focused
            e['EnjoymentPaused'] = focused
            e['_TimerPaused'] = focused
        e['timerPaused'] = value
    e['SetFixedLengthTimerPaused'] = reacquire_during_pause
    e['OpenSceneSelect']()
    assert e['_bFocusedSceneHUD'] == e['EnjoymentPaused'] == e['_TimerPaused'] == e['timerPaused'] == focused

# MCM refresh: release at both unregister and register boundaries. Include a
# late RegisterForKey completion after DisableHotkeys has removed registrations.
e, calls, registered, settings = fixture()
settings['iOpenSceneSelect'] = 34
e['RegisterHotkeys']()
old_controls = e['Hotkeys'][:10]
e['GetAdjustPos'] = lambda: (_ for _ in ()).throw(AssertionError('Refresh must not reselect the target'))
e['Config'].FocusSceneHUD = 88
settings['iOpenSceneSelect'] = 35
e['RefreshSceneSelectHotkey']()
assert e['Hotkeys'][:10] == old_controls and 184 in registered and 88 not in registered

for boundary in ('UnregisterForKey', 'RegisterForKey'):
    for release_first in (False, True):
        e, calls, registered, settings = fixture()
        settings['iOpenSceneSelect'] = 34
        e['RegisterHotkeys']()
        settings['iOpenSceneSelect'] = 35
        native = getattr(e['Config'], boundary)
        fired = [False]

        def interrupted_key(key, native=native, release_first=release_first):
            if not fired[0]:
                fired[0] = True
                if release_first:
                    release_control(e, registered)
                    native(key)
                else:
                    native(key)
                    release_control(e, registered)
            else:
                native(key)

        setattr(e['Config'], boundary, interrupted_key)
        e['RefreshSceneSelectHotkey']()
        assert fired[0] and not registered, (boundary, registered)

# A new session may own the same key: stale completion must not unregister it.
for next_key in (35, 36):
    e, calls, registered, settings = fixture()
    settings['iOpenSceneSelect'] = 34
    e['RegisterHotkeys']()
    settings['iOpenSceneSelect'] = 35
    def reacquire_during_registration(key):
        release_control(e, registered)
        e['_SceneSelectRevision'] += 1
        e['_SceneHotkeysEnabled'] = True
        e['Hotkeys'] = [184] + [-1] * 9 + [next_key]
        registered.update((184, next_key, key))
    e['Config'].RegisterForKey = reacquire_during_registration
    e['RefreshSceneSelectHotkey']()
    assert registered == {184, next_key}

# Late unregister must not remove a key legitimately reused by the new session.
for next_key in (34, 36):
    e, calls, registered, settings = fixture()
    settings['iOpenSceneSelect'] = 34
    e['RegisterHotkeys']()
    settings['iOpenSceneSelect'] = 35
    def reacquire_during_unregister(key):
        release_control(e, registered)
        e['_SceneSelectRevision'] += 1
        e['_SceneHotkeysEnabled'] = True
        e['Hotkeys'] = [184] + [-1] * 9 + [next_key]
        registered.update((184, next_key))
        registered.discard(key)
    e['Config'].UnregisterForKey = reacquire_during_unregister
    e['RefreshSceneSelectHotkey']()
    assert registered == {184, next_key}

assert controller.index('Function HandleSceneSelectMainKey') < controller.index('If (_bFocusedSceneHUD || _bOpenedSceneGraph)')
assert 'MCM_SETTING(iOpenSceneSelect, -1)' in (ROOT / 'src/UserData/mcm.def').read_text()
for lang in ('ENGLISH', 'CHINESE'):
    table = (ROOT / f'dist/Interface/Translations/SexLab_{lang}.txt').read_text(encoding='utf-16')
    for key in ('iOpenSceneSelect', 'iOpenSceneSelectHighlight', 'SceneSelectKeyConflict'):
        assert table.count('$SSL_' + key + '\t') == 1
print('PASS: extracted Papyrus registration, MCM bind/rebind/unbind/conflicts, focus and lifecycle cases; native C++ ' + ('SKIPPED (no compilation)' if '--papyrus-only' in sys.argv else 'passed'))
