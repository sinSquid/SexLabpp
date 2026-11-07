"""Execute selection/queue PSC bodies in Python; never invoke compilers."""
from pathlib import Path
import runpy
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
previous = sys.argv
try:
    sys.argv = ['scene_select_hotkey.py', '--papyrus-only']
    m = runpy.run_path(str(ROOT / 'tests/scene_select_hotkey.py'))
finally:
    sys.argv = previous
model = (ROOT / 'dist/Source/Scripts/sslThreadModel.psc').read_text(encoding='utf-8')
select = m['translated_body'](m['controller'], 'SelectSceneFromHUD')
queued = m['translated_body'](model, 'GetQueuedSceneReset')
# Types are erased by this translator; this replacement only permits parsing.
real_reset = m['translated_body'](model.replace('float now =', 'int now ='), 'ResetScene')


def execute(code, env):
    try:
        exec(code, env)
    except m['Returned'] as result:
        return result.value


def click(env, scene='new'):
    return scene, env['SceneSelectUIRevision'], env['SceneSelectAutoClose']


def deliver(env, selection):
    env['asSceneId'], env['aiUIRevision'], env['abAutoClose'] = selection
    execute(select, env)


def fixture():
    e, calls, _, _ = m['fixture']()
    active = ['old']
    e['_queuedSceneReset'] = ''
    e['GetQueuedSceneReset'] = lambda: execute(queued, e)
    e['GetActiveScene'] = lambda: active[0]
    def reset(scene):
        calls.append(('reset', scene))
        active[0] = scene
        return True
    e['ResetScene'] = reset
    return e, calls


for shortcut in (False, True):
    e, calls = fixture()
    if shortcut:
        e['OpenSceneSelect']()
    else:
        e['_bOpenedSceneHUD'] = True
        e['ToggleFocusSceneHUD'](1)
    selection = click(e)
    calls.clear()
    deliver(e, selection)
    assert ('reset', 'new') in calls
    assert e['_bFocusedSceneHUD'] != shortcut and e['timerPaused'] != shortcut

for same, accepted in ((True, True), (False, False)):
    e, calls = fixture()
    e['OpenSceneSelect']()
    if not accepted:
        e['ResetScene'] = lambda scene: False
    deliver(e, click(e, 'old' if same else 'new'))
    assert e['_bFocusedSceneHUD']

# Queued click across every Alt/shortcut close-and-reopen combination.
for old_shortcut in (False, True):
    for new_shortcut in (False, True):
        e, calls = fixture()
        e['_bOpenedSceneHUD'] = True
        (e['OpenSceneSelect'] if old_shortcut else lambda: e['ToggleFocusSceneHUD'](1))()
        selection = click(e)
        e['ToggleFocusSceneHUD'](-1)
        (e['OpenSceneSelect'] if new_shortcut else lambda: e['ToggleFocusSceneHUD'](1))()
        calls.clear()
        deliver(e, selection)
        assert e['_bFocusedSceneHUD'] and not calls, (old_shortcut, new_shortcut, calls)

# Reset itself yields across manual close/reopen through either entry.
for new_shortcut in (False, True):
    e, calls = fixture()
    e['OpenSceneSelect']()
    selection = click(e)
    def delayed_reset(scene):
        e['ToggleFocusSceneHUD'](-1)
        (e['OpenSceneSelect'] if new_shortcut else lambda: e['ToggleFocusSceneHUD'](1))()
        calls.clear()
        return True
    e['ResetScene'] = delayed_reset
    deliver(e, selection)
    assert e['_bFocusedSceneHUD'] and ('focus', -1) not in calls

# Real ResetScene returns true for ignored AND queued requests; distinguish them.
for pending, settling, expected_close in ((False, True, False), (True, False, True)):
    e, calls = fixture()
    e['OpenSceneSelect']()
    e.update(_sceneResetSyncPending=settling, _nextSceneResetAt=0,
             _animationSyncPending=pending, SexLabUtil=m['SimpleNamespace'](GetCurrentGameRealTime=lambda: 1),
             Log=lambda *args: None)
    def reset(scene):
        e['asNewScene'] = scene
        return execute(real_reset, e)
    e['ResetScene'] = reset
    deliver(e, click(e))
    assert e['GetActiveScene']() == 'old'
    assert e['_bFocusedSceneHUD'] != expected_close
    assert (e['_queuedSceneReset'] == 'new') == pending

e, calls = fixture()
e['OpenSceneSelectImpl'] = lambda: False
e['OpenSceneSelect']()
assert not e['SceneSelectAutoClose']

panel = (ROOT / 'src/Thread/Interface/Elements/SceneSelectPanel.cpp').read_text(encoding='utf-8')
assert re.search(r'DispatchMethodCall\([^;]*"SelectSceneFromHUD",\s*a_hud.GetCallback\(\),\s*RE::BSFixedString\{ a_sceneId.c_str\(\) \}, uiRevision, autoClose\)', panel)
assert 'GetProperty<int>(a_hud.GetThreadScript(), "SceneSelectUIRevision")' in panel
assert 'GetProperty<bool>(a_hud.GetThreadScript(), "SceneSelectAutoClose")' in panel
signature = re.search(r'^Function SelectSceneFromHUD\(([^)]*)\)', m['controller'], re.M)[1]
assert len(signature.split(',')) == 3 and 'if (clicked && !e.isActive)' in panel
print('PASS: click origin/UI ticket, all reopen combinations, delayed reset, ignored vs queued real ResetScene, native/PSC three-argument contract')
