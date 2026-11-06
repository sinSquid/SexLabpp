"""Pure Python execution of actual PSC bodies. Never invokes a compiler."""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
previous = sys.argv
try:
    sys.argv = ['scene_select_hotkey.py', '--papyrus-only']
    m = runpy.run_path(str(ROOT / 'tests/scene_select_hotkey.py'))
finally:
    sys.argv = previous

thread_keys = m['translated_body'](m['controller'], 'OnKeyDown')
global_keys = m['translated_body'](m['system'], 'OnKeyDown')


def run(code, scope):
    try:
        exec(code, scope)
    except m['Returned'] as result:
        return result.value


def setup():
    e, calls, registered, settings = m['fixture']()
    e.update(_SkipHotkeyEvents=False, pressedKeys=set(), aiKey=24)
    e['Config'].ModifierPressed = lambda: False
    e['PickRandomScene'] = lambda scene: calls.append('random')
    e['OpenSceneSelectImpl'] = lambda: calls.append('scenes') or True
    settings.update(iOpenSceneSelect=24, iSceneSelectModifier=29, iChangeAnimation=24,
                    iKeyMod=42, iKeyAdvance=57, iTargetActor=49)
    e['IsSceneSelectMainKey'] = e['Config'].IsSceneSelectMainKey
    e['IsSceneSelectModifier'] = e['Config'].IsSceneSelectModifier
    e['HandleGlobalHotkey'] = e['Config'].HandleGlobalHotkey
    def handle_main(key):
        e['aiKey'] = key
        run(m['bodies']['HandleSceneSelectMainKey'], e)
    e['HandleThreadHotkey'] = lambda key: run(m['bodies']['HandleThreadHotkey'], dict(e, aiKey=key))
    e['_ActiveControl'] = m['SimpleNamespace'](HandleSceneSelectMainKey=handle_main)
    e['RegisterHotkeys']()
    return e, calls, registered, settings


def press(e, global_first=False, between=lambda: None):
    e['keyCode'] = e['aiKey']
    first, second = (global_keys, thread_keys) if global_first else (thread_keys, global_keys)
    run(first, e)
    between()
    run(second, e)


e, calls, registered, settings = setup()
press(e)
assert calls == ['random'] # Same main key keeps its original action without modifier.
calls.clear()
e['pressedKeys'] = {29}
e['aiKey'] = 29
press(e)
assert not calls # Modifier alone never triggers the Scenes shortcut.
e['aiKey'] = 24
press(e)
assert 'scenes' in calls and 'random' not in calls

# Changing/clearing the modifier is live: no re-registration required.
e, calls, registered, settings = setup()
settings['iSceneSelectModifier'] = 30
e['pressedKeys'] = {29}
press(e)
assert calls == ['random']
calls.clear()
e['pressedKeys'] = {30}
press(e)
assert 'scenes' in calls
e, calls, registered, settings = setup()
settings['iSceneSelectModifier'] = -1
press(e)
assert 'scenes' in calls and 'random' not in calls

# Rebind the shared key: its old ordinary action must stay registered.
e, calls, registered, settings = setup()
settings['iOpenSceneSelect'] = 35
e['RefreshSceneSelectHotkey']()
assert 24 in registered and 35 in registered
settings['iOpenSceneSelect'] = -1
e['RefreshSceneSelectHotkey']()
assert 24 in registered and 35 not in registered
assert not e['Config'].IsSceneSelectModifier(29)

# Complete binding conflicts, including reverse changes and modifier removal.
e, calls, registered, settings = setup()
conflict = e['Config'].HasSceneSelectKeyConflict
assert not conflict('iOpenSceneSelect', 24) # Ctrl+O can reuse O.
assert conflict('iSceneSelectModifier', 24) # Same physical key forbidden.
assert conflict('iSceneSelectModifier', -1) # Clearing modifier would collide with O.
settings['iOpenSceneSelect'] = 57
assert not conflict('iSceneSelectModifier', 29) # Ctrl+Space differs from Shift+Space.
assert conflict('iSceneSelectModifier', 42) # Legacy Shift+Space already advances backward.
assert conflict('iKeyMod', 29) # Changing old modifier must not silently create collision.
settings.update(iOpenSceneSelect=35, iSceneSelectModifier=29)
assert conflict('iKeyAdvance', 35) is False
settings['iSceneSelectModifier'] = 42
assert conflict('iKeyAdvance', 35)

# Global TFC/control keys must not also execute when used by the active chord.
e, calls, registered, settings = setup()
settings['iOpenSceneSelect'] = 81
e['pressedKeys'] = {29}
e.update(keyCode=81, ToggleFreeCamera=81, TargetActor=49, ToggleThreadControl=21,
         IsSceneSelectModifier=e['Config'].IsSceneSelectModifier,
         IsSceneSelectShortcut=e['Config'].IsSceneSelectShortcut)
e['SexLabUtil'].ToggleFreeCamera = lambda: calls.append('camera')
e['RefreshSceneSelectHotkey']()
e['aiKey'] = 81
press(e)
assert 'scenes' in calls and 'camera' not in calls
calls.clear()
e['pressedKeys'].clear()
press(e)
assert calls == ['camera']
calls.clear()
settings.update(iOpenSceneSelect=35, iSceneSelectModifier=81)
e['aiKey'] = 81
e['keyCode'] = 81
run(global_keys, e)
assert not calls # A configured global-key modifier is reserved during playback.
e['_ActiveControl'] = False
run(global_keys, e)
assert calls == ['camera'] # Outside thread control the old global binding is unchanged.

# Same main press, separate VM handlers: release the modifier between them.
for global_first in (False, True):
    for held in (False, True):
        e, calls, registered, settings = setup()
        settings['iOpenSceneSelect'] = 81
        e['RefreshSceneSelectHotkey']()
        e['SexLabUtil'].ToggleFreeCamera = lambda: calls.append('camera')
        e['pressedKeys'] = {29} if held else set()
        e['aiKey'] = 81
        press(e, global_first=global_first, between=lambda: e['pressedKeys'].clear())
        # The global handler is the sole owner, regardless of execution order.
        assert not ('scenes' in calls and 'camera' in calls), (global_first, held, calls)
        assert calls.count('scenes') + calls.count('camera') == 1, calls

# Also retain ordinary global behavior without an active animation controller.
e, calls, registered, settings = setup()
settings['iOpenSceneSelect'] = 81
e['_ActiveControl'] = False
e['SexLabUtil'].ToggleFreeCamera = lambda: calls.append('camera')
e['aiKey'] = 81
press(e)
assert calls == ['camera']

assert 'MCM_SETTING(iSceneSelectModifier, -1)' in (ROOT / 'src/UserData/mcm.def').read_text()
native = (ROOT / 'src/Thread/Interface/SceneHUD.cpp').read_text()
assert native.index('if (IsSceneSelectKey(key, *a_event))') < native.index('const bool increase = key == kRightArrow')
assert native.index('pressed = button->IsPressed()') < native.index('input->GetKeyboard()')
print('PASS: single/chord input, live modifier changes, shared-key registration, pair conflicts and global-key isolation; native source contract only, no compilation')
