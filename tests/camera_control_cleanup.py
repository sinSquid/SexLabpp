"""Execute production PSC helpers with API stand-ins, not the Papyrus VM."""
from types import SimpleNamespace as NS
from papyrus_harness import helper, body, source, Array
from unittest.mock import patch
import re


def test_release():
    for movement in (0, 1):
        calls = []
        player = object()
        def force():
            raise AssertionError('input release must not wait for the camera')
        game = NS(GetPlayer=lambda: player, GetCameraState=lambda: 0,
                  ForceThirdPerson=force,
                  SetPlayerAIDriven=lambda x: calls.append(('ai', x)),
                  EnablePlayerControls=lambda **kw: calls.append(('enable', kw)))
        release = helper('SexLabUtil', 'SetActorMovement', 'akActor, aiMovement',
                         dict(Game=game, GetConfig=lambda: NS(HasVRIK=False)))
        release(player, movement)
        assert calls[0] == ('ai', False)
        assert calls[1][0] == 'enable'
        assert calls[1][1] == ({} if movement == 0 else dict(
            abFighting=False, abCamSwitch=False, abSneaking=False, abActivate=False))


def test_camera():
    for mode in ('ready', 'recovers', 'stuck', 'cancelled'):
        state = dict(camera=9 if mode == 'ready' else 0, attempts=0, valid=True)
        def force():
            state['attempts'] += 1
            if mode == 'recovers':
                state['camera'] = 9
        def wait(_):
            if mode == 'cancelled':
                state['valid'] = False
        thread = NS(IsActorControlRequestCurrent=lambda *a: state['valid'])
        camera = helper('SexLabUtil', 'TryForceThirdPerson', 'akThread, aiRevision, akActor, aiCameraRequestRevision=-1', dict(
            GetConfig=lambda: NS(HasVRIK=False),
            Game=NS(GetCameraState=lambda: state['camera'], ForceThirdPerson=force),
            Utility=NS(WaitMenuMode=wait), Debug=NS(Trace=lambda *a: None)))
        assert camera(thread, 1, object()) == (mode in ('ready', 'recovers'))
        assert state['attempts'] <= 20
        if mode == 'cancelled':
            assert state['attempts'] == 1


def test_lifecycle():
    for state in ('Making_M', 'Animating', 'Ending', 'Unlocked', 'Making'):
        env = dict(LifecycleRevision=7, GetState=lambda: state,
                   STATE_SETUP_M='Making_M', STATE_PLAYING='Animating',
                   HasActor=lambda actor: actor == 'player')
        current = helper('sslThreadModel', 'IsActorControlRequestCurrent', 'akActor, aiRevision', env)
        assert current('player', 7) == (state in ('Making_M', 'Animating'))
        assert not current('player', 6)
        assert not current('removed', 7)


def test_ownership():
    this = object()
    other = object()
    for owner, controlled, expected in ((None, None, True), (this, this, True),
                                        (other, None, False), (None, other, False)):
        config = NS(ThreadSlots=NS(GetThreadByActor=lambda actor: owner),
                    GetThreadControlled=lambda: controlled)
        can_release = helper('sslThreadModel', 'CanReleaseActorControl', 'akActor', dict(
            Config=config, Self=this, PlayerRef='player'))
        assert can_release('player') == expected


def test_stale_lock():
    for cancel in (False, True):
        calls = []
        actor = object()
        state = dict(valid=True)
        def camera(*_):
            if cancel:
                state['valid'] = False
            return not cancel
        thread = NS(LifecycleRevision=3,
                    IsActorControlRequestCurrent=lambda *a: state['valid'],
                    UpdateAnimatingActorMovement=lambda a: calls.append('lock'))
        lock = helper('sslActorAlias', 'NativeActorLockApplied', '', dict(
            _ActorLocked=False, _ActorRef=actor, _PlayerRef=actor, _Thread=thread,
            _Config=NS(HasVRIK=False, AutoTFC=True, VRIK_FPP_HMD=0, ToggleVRIK=lambda *a: None),
            SexLabUtil=NS(TryForceThirdPerson=camera, EnableSceneFreeCamera=lambda *a: calls.append('camera')),
            Log=lambda *a: None, GetActorName=lambda: 'player'), ('_ActorLocked',))
        lock()
        assert calls == ([] if cancel else ['lock', 'camera'])
        assert lock.__globals__['_ActorLocked'] == (not cancel)


def test_stale_preparation():
    for name in ('PrepareDone', 'OnPlayerSheatheComplete'):
        calls = []
        state = dict(revision=4, phase='Making_M')
        def lock():
            # End or recycle the thread while camera switching yields.
            state.update(revision=5, phase='Ending')
            fn.__globals__['LifecycleRevision'] = 5
        env = dict(LifecycleRevision=4, _prepareAsyncCount=1, _Positions=Array(['player']),
                   Log=lambda *a: None, HasPlayer=True, PlayerRef='player',
                   STATE_SETUP_M='Making_M', GetState=lambda: state['phase'],
                   BeginPlayerSheatheWait=lambda: True,
                   ActorAlias=lambda a: NS(NativeActorLockApplied=lock),
                   FinishPreparation=lambda: calls.append('finish'), EndAnimation=lambda: None)
        fn = helper('sslThreadModel', name, '' if name == 'PrepareDone' else 'abSucceeded', env,
                    ('_prepareAsyncCount',))
        fn(*(() if name == 'PrepareDone' else (True,)))
        assert calls == []


def test_free_camera():
    for valid, camera_state in ((False, 9), (True, 0), (True, 3), (True, 9)):
        calls = []
        fn = helper('SexLabUtil', 'EnableSceneFreeCamera', 'akThread, aiRevision, akActor', dict(
            Game=NS(GetCameraState=lambda: camera_state), GetConfig=lambda: NS(AutoSUCSM=5, FreeCameraRequestRevision=0),
            MiscUtil=NS(SetFreeCameraSpeed=lambda x: None, ToggleFreeCamera=lambda: calls.append('tfc'))))
        fn(NS(IsActorControlRequestCurrent=lambda *a: valid), 2, 'player')
        assert calls == (['tfc'] if valid and camera_state == 9 else [])


def test_early_cleanup():
    # Execute the Paused-state implementation, including a failing redress.
    paused = source('sslActorAlias').split('State Paused', 1)[1]
    clear_body = re.search(r'Function Clear\(\)\s*\n(.*?)EndFunction', paused, re.S)[1]
    calls = []
    class RedressFailed(Exception):
        pass
    def redress():
        raise RedressFailed()
    with patch('papyrus_harness.body', return_value=clear_body):
        clear = helper('sslActorAlias', 'Clear', '', dict(
            _ActorRef='player', _PlayerRef='player', _ActorLocked=False, _sex=1,
            _Thread=NS(ReleaseActorControl=lambda actor: calls.append('release')), Redress=redress))
    try:
        clear()
    except RedressFailed:
        pass
    assert calls == ['release']
    for allowed in (False, True):
        calls = []
        actor = NS(SetFactionRank=lambda *a: calls.append('faction'),
                   EvaluatePackage=lambda: calls.append('package'))
        release = helper('sslThreadModel', 'ReleaseActorControl', 'akActor', dict(
            CanReleaseActorControl=lambda a: allowed, Config=NS(AnimatingFaction=object()),
            SexLabUtil=NS(SetActorMovement=lambda *a: calls.append('release'))))
        release(actor)
        release(actor)
        assert calls == (['faction', 'release', 'package'] * 2 if allowed else [])


def test_interrupted_waits():
    for cancelled_at in (1, 2, None):
        state = dict(revision=8, waits=0)
        calls = []
        def wait(_):
            state['waits'] += 1
            if state['waits'] == cancelled_at:
                fn.__globals__['LifecycleRevision'] = 9
        alias = NS(InitiateUndressing=lambda: True, ReadyActor=lambda *a: calls.append('ready'))
        env = dict(LifecycleRevision=8, _Positions=Array(['player']),
                   ActorAlias=Array([alias]), Utility=NS(Wait=wait),
                   GetState=lambda: 'Making_M', STATE_SETUP_M='Making_M', STATE_PLAYING='Animating',
                   HasPlayer=True, sslSystemConfig=NS(GetSettingInt=lambda _: 0),
                   GetActiveScene=lambda: 'scene', GoToState=lambda s: calls.append(s),
                   SexLabRegistry=NS(GetStripDataA=lambda *a: [0], GetPositionSexA=lambda *a: [0]))
        fn = helper('sslThreadModel', 'UndressAndStripActors', '', env)
        fn()
        assert calls == ({1: [], 2: ['ready'], None: ['ready', 'Animating']}[cancelled_at])


def test_cancelled_manual_camera():
    revision = helper('sslSystemConfig', 'NextFreeCameraRequest', '', dict(
        _FreeCameraRequestRevision=0), ('_FreeCameraRequestRevision',))
    assert [revision(), revision(), revision()] == [1, 2, 3]
    for close_at in ('wait', 'wait_stuck', 'speed', 'newer', None):
        state = dict(camera=0, attempts=0)
        calls = []
        config = NS(HasVRIK=False, POVModeVR=0, AutoSUCSM=5, FreeCameraRequestRevision=0)
        def next_request():
            config.FreeCameraRequestRevision += 1
            return config.FreeCameraRequestRevision
        config.NextFreeCameraRequest = next_request
        def close():
            toggle(0)
        def wait(_):
            if close_at in ('wait', 'wait_stuck'):
                close()  # Exit cleanup runs before the camera becomes third person.
            if close_at == 'wait_stuck':
                return
            state['camera'] = 9
            if close_at == 'newer':
                toggle(1)  # A fresh enable request must survive the old request returning.
        def speed(_):
            if close_at == 'speed':
                close()
        def force():
            state['attempts'] += 1
        game = NS(GetCameraState=lambda: state['camera'], ForceThirdPerson=force)
        third_person = helper('SexLabUtil', 'TryForceThirdPerson', 'akThread, aiRevision, akActor, aiCameraRequestRevision=-1', dict(
            GetConfig=lambda: config, Game=game, Utility=NS(WaitMenuMode=wait),
            Debug=NS(Trace=lambda *a: None)))
        def toggle_native():
            calls.append('toggle')
            state['camera'] = 9 if state['camera'] == 3 else 3
        toggle = helper('SexLabUtil', 'ToggleFreeCamera', 'aiForceState', dict(
            GetConfig=lambda: config, Game=game,
            TryForceThirdPerson=lambda **kw: third_person(None, 0, None, **kw),
            MiscUtil=NS(SetFreeCameraSpeed=speed, ToggleFreeCamera=toggle_native)))
        toggle(-1)
        assert calls == (['toggle'] if close_at in (None, 'newer') else []), close_at
        assert state['attempts'] == 1
        # A fresh request after cancellation must still work.
        state['camera'] = 3 if close_at == 'newer' else 9
        toggle.__globals__['MiscUtil'].SetFreeCameraSpeed = lambda _: None
        toggle(1)
        assert state['camera'] == 3
        toggle(0)
        assert state['camera'] == 9


def test_interrupted_fade():
    for cancellation in ('revision', 'state', None):
        calls = []
        state = dict(phase='Making_M')
        def fade():
            if cancellation == 'revision':
                fn.__globals__['LifecycleRevision'] = 9
            if cancellation == 'state':
                state['phase'] = 'Ending'
        alias = NS(InitiateUndressing=lambda: False, ReadyActor=lambda *a: calls.append('ready'))
        fn = helper('sslThreadModel', 'UndressAndStripActors', '', dict(
            LifecycleRevision=8, _Positions=Array(['player']), ActorAlias=Array([alias]),
            GetState=lambda: state['phase'], STATE_SETUP_M='Making_M', STATE_PLAYING='Animating',
            HasPlayer=True, sslSystemConfig=NS(GetSettingInt=lambda _: 1), Config=NS(ApplyFade=fade),
            GetActiveScene=lambda: calls.append('query') or 'scene',
            SexLabRegistry=NS(GetStripDataA=lambda *a: [0], GetPositionSexA=lambda *a: [0]),
            GoToState=lambda s: calls.append(s)))
        fn()
        assert calls == ([] if cancellation else ['query', 'ready', 'Animating']), cancellation


def test_manual_automatic_camera_overlap():
    for force_state in (-1, 1):
        for automatic_at in ('wait', 'speed'):
            state = dict(camera=0, automatic_started=False)
            calls = []
            config = NS(HasVRIK=False, POVModeVR=0, AutoSUCSM=5, FreeCameraRequestRevision=0)
            def next_request():
                config.FreeCameraRequestRevision += 1
                return config.FreeCameraRequestRevision
            config.NextFreeCameraRequest = next_request
            def toggle_native():
                state['camera'] = 9 if state['camera'] == 3 else 3
                calls.append(state['camera'])
            def automatic():
                if not state['automatic_started']:
                    state['automatic_started'] = True
                    scene(NS(IsActorControlRequestCurrent=lambda *a: True), 2, 'player')
            def wait(_):
                state['camera'] = 9
                if automatic_at == 'wait':
                    automatic()
            def speed(_):
                if automatic_at == 'speed':
                    automatic()
            game = NS(GetCameraState=lambda: state['camera'], ForceThirdPerson=lambda: None)
            misc = NS(SetFreeCameraSpeed=speed, ToggleFreeCamera=toggle_native)
            scene = helper('SexLabUtil', 'EnableSceneFreeCamera', 'akThread, aiRevision, akActor', dict(
                GetConfig=lambda: config, Game=game, MiscUtil=misc))
            third_person = helper('SexLabUtil', 'TryForceThirdPerson',
                'akThread, aiRevision, akActor, aiCameraRequestRevision=-1', dict(
                    GetConfig=lambda: config, Game=game, Utility=NS(WaitMenuMode=wait),
                    Debug=NS(Trace=lambda *a: None)))
            toggle = helper('SexLabUtil', 'ToggleFreeCamera', 'aiForceState', dict(
                GetConfig=lambda: config, Game=game, MiscUtil=misc,
                TryForceThirdPerson=lambda **kw: third_person(None, 0, None, **kw)))
            toggle(force_state)
            assert state['camera'] == 3 and calls == [3], (force_state, automatic_at, calls)
            toggle(1)  # Force-on while already free is still idempotent.
            assert calls == [3]
            toggle(-1)  # A new, deliberate toggle still closes it normally.
            assert state['camera'] == 9 and calls == [3, 9]


def test_automatic_manual_camera_overlap():
    state = dict(camera=9, manual_started=False)
    calls = []
    config = NS(HasVRIK=False, AutoSUCSM=5, FreeCameraRequestRevision=0)
    def next_request():
        config.FreeCameraRequestRevision += 1
        return config.FreeCameraRequestRevision
    config.NextFreeCameraRequest = next_request
    def speed(_):
        if not state['manual_started']:
            state['manual_started'] = True
            toggle(1)
    def toggle_native():
        state['camera'] = 9 if state['camera'] == 3 else 3
        calls.append(state['camera'])
    game = NS(GetCameraState=lambda: state['camera'])
    misc = NS(SetFreeCameraSpeed=speed, ToggleFreeCamera=toggle_native)
    toggle = helper('SexLabUtil', 'ToggleFreeCamera', 'aiForceState', dict(
        GetConfig=lambda: config, Game=game, MiscUtil=misc, TryForceThirdPerson=lambda **kw: True))
    scene = helper('SexLabUtil', 'EnableSceneFreeCamera', 'akThread, aiRevision, akActor', dict(
        GetConfig=lambda: config, Game=game, MiscUtil=misc))
    scene(NS(IsActorControlRequestCurrent=lambda *a: True), 2, 'player')
    assert calls == [3] and state['camera'] == 3, calls


def test_automatic_camera_cancelled_by_manual_close():
    state = dict(camera=9, close_requested=False)
    calls = []
    config = NS(HasVRIK=False, AutoSUCSM=5, FreeCameraRequestRevision=0)
    def next_request():
        config.FreeCameraRequestRevision += 1
        return config.FreeCameraRequestRevision
    config.NextFreeCameraRequest = next_request
    def speed(_):
        if not state['close_requested']:
            state['close_requested'] = True
            manual(0)
    def toggle_native():
        state['camera'] = 9 if state['camera'] == 3 else 3
        calls.append(state['camera'])
    game = NS(GetCameraState=lambda: state['camera'])
    misc = NS(SetFreeCameraSpeed=speed, ToggleFreeCamera=toggle_native)
    manual = helper('SexLabUtil', 'ToggleFreeCamera', 'aiForceState', dict(
        GetConfig=lambda: config, Game=game, MiscUtil=misc, TryForceThirdPerson=lambda **kw: True))
    scene = helper('SexLabUtil', 'EnableSceneFreeCamera', 'akThread, aiRevision, akActor', dict(
        GetConfig=lambda: config, Game=game, MiscUtil=misc))
    thread = NS(IsActorControlRequestCurrent=lambda *a: True)
    scene(thread, 2, 'player')
    assert state['close_requested'] and state['camera'] == 9 and calls == [], calls
    # Cancellation invalidates that request, without permanently disabling fresh opens.
    scene(thread, 2, 'player')
    assert state['camera'] == 3 and calls == [3]
    manual(0)
    assert state['camera'] == 9 and calls == [3, 9]


test_release()
test_camera()
test_lifecycle()
test_ownership()
test_stale_lock()
test_stale_preparation()
test_free_camera()
test_early_cleanup()
test_interrupted_waits()
test_cancelled_manual_camera()
test_interrupted_fade()
test_manual_automatic_camera_overlap()
test_automatic_manual_camera_overlap()
test_automatic_camera_cancelled_by_manual_close()
assert 'ReleaseActorControl' in body('sslActorAlias', 'Clear')
print('PASS: camera-independent release, bounded/cancelled camera, lifecycle, ownership and stale startup')
