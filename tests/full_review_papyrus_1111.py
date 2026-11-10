"""Extracted production PSC regressions; no compiler, VM or game execution.

--baseline-ref HEAD reads the pre-fix tracked scripts for red/green comparison.
Latent-call stand-ins inject cancellation and quest/alias reuse at real waits.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import itertools
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()


def source(name):
    path = 'dist/Source/Scripts/' + name + '.psc'
    if args.baseline_ref:
        return subprocess.check_output(['git', 'show', args.baseline_ref + ':' + path], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8-sig')


engine = {'__file__': str(ROOT / 'tests/papyrus_confirmed_regressions.py')}
text = (ROOT / 'tests/papyrus_confirmed_regressions.py').read_text(encoding='utf-8')
argv = sys.argv
try:
    sys.argv = [argv[0]]
    # Share the execution scope so a latent call can mutate the live script.
    exec(text[:text.index('\nutility = NS(')].replace('scope = dict(env)', 'scope = env'), engine)
finally:
    sys.argv = argv
engine['source'] = source
Array = engine['Array']


def call(name, function, env, occurrence=0):
    return engine['execute'](without_diagnostics(engine['body'](name, function, occurrence)).replace('prepareRevision as string', 'str(prepareRevision)'), env)


def without_diagnostics(body):
    # Papyrus implicitly stringifies numbers in logging expressions; diagnostic
    # formatting is outside this fixture's state/return contract.
    return re.sub(r'(?m)^(\s*)(?:Log|Error)\([^\n]*\)\s*$', r'\1pass', body)


def event(name, function, env, occurrence=0):
    matches = re.findall(r'(?ims)^\s*Event\s+' + function + r'\([^\n]*\)\s*\n(.*?)^\s*EndEvent', source(name))
    return engine['execute'](without_diagnostics(matches[occurrence]), env)


class PapyrusReviewRegressions(unittest.TestCase):
    def test_find_bed_flags_and_ignored_refs(self):
        occupied, free, other = object(), object(), object()
        for ignore_used, ignored in itertools.product((False, True), (None, occupied, free)):
            with self.subTest(ignore_used=ignore_used, ignored=ignored):
                env = dict(CenterRef=object(), Radius=1000, IgnoreUsed=ignore_used,
                           IgnoreRef1=ignored, IgnoreRef2=other,
                           FindBeds=lambda *a: Array([occupied, free, other]),
                           IsBedAvailable=lambda bed: bed is free)
                result, _ = call('sslThreadLibrary', 'FindBed', env)
                expected = next((bed for bed in (occupied, free) if bed is not ignored and
                                 (not ignore_used or bed is free)), None)
                self.assertIs(result, expected)

    def test_tag_truth_table(self):
        for tags, present, require_all, suppress in itertools.product(
                ([], ['a'], ['a', 'b']), (set(), {'a'}, {'a', 'b'}), (False, True), (False, True)):
            with self.subTest(tags=tags, present=present, all=require_all, suppress=suppress):
                matches = [tag in present for tag in tags]
                expected = (all(matches) if require_all else any(matches)) != suppress
                result, _ = call('sslThreadModel', 'CheckTags', dict(
                    CheckTags=Array(tags), RequireAll=require_all, Suppress=suppress,
                    HasTag=lambda tag: tag in present))
                self.assertEqual(result, expected)

    def test_move_wait_cancellation_and_normal_completion(self):
        # Normal: initial wait, key-wait, momentum wait, moving-momentum wait.
        for cancel_at in (None, 1, 2, 3, 4):
            for reuse in (False, True):
                with self.subTest(cancel_at=cancel_at, reuse=reuse):
                    effects, waits = [], []
                    player = NS(X=0, Y=0, Z=0)
                    state = dict(revision=7, phase='Animating', cancelled=False)
                    env = dict(PlaybackRevision=7, Positions=Array(), PlayerRef=player,
                               IsCurrentPlayback=lambda rev: rev == state['revision'] and state['phase'] == 'Animating',
                               SexLabRegistry=NS(IsCompatibleCenter=lambda *a: True),
                               Game=NS(GetPlayer=lambda: player), GetActiveScene=lambda: 'scene',
                               UnregisterForUpdate=lambda: None, _bOpenedSceneHUD=False,
                               StorageUtil=NS(GetIntValue=lambda *a: 1), HasPlayer=True,
                               Config=NS(MoveScene=10),
                               Input=NS(IsKeyPressed=lambda _: len(waits) >= 2),
                               SexLabUtil=NS(SetActorMovement=lambda actor, mode: effects.append(('movement', mode))),
                               CenterOnObject=lambda _: effects.append(('center', None)))

                    def wait(delay):
                        waits.append(delay)
                        self.assertLess(len(waits), 8, 'relocation wait became unbounded')
                        if len(waits) == 3:
                            player.X = 1  # one momentum iteration
                        if len(waits) == cancel_at:
                            state.update(revision=8 if not reuse else 9,
                                         phase='Unlocked' if not reuse else 'Animating', cancelled=True)
                            effects.append(('cancel-and-release', 0))

                    env['Utility'] = NS(Wait=wait)
                    call('sslThreadController', 'MoveScene', env)
                    if cancel_at is None:
                        self.assertEqual(effects, [('movement', 1), ('movement', 2), ('center', None)])
                        self.assertEqual(len(waits), 4)
                    else:
                        marker = effects.index(('cancel-and-release', 0))
                        self.assertEqual(effects[marker + 1:], [], 'stale relocation mutated ended/reused session')

    def test_preparation_wait_cancellation_and_completion(self):
        for cancel_at, phase, reuse in itertools.product((None, 1, 2), ('Unlocked', 'Ending', 'Making_M'), (False, True)):
            with self.subTest(cancel_at=cancel_at, phase=phase, reuse=reuse):
                effects, waits = [], []
                actor = object()
                state = dict(revision=5, phase='Making_M')
                alias = NS(InitiateUndressing=lambda: True,
                           ReadyActor=lambda *a: effects.append('ready'))
                env = dict(SetupRevision=5, aiRevision=5, _Positions=Array([actor]), ActorAlias=Array([alias]),
                           IsCurrentPreparation=lambda rev: rev == state['revision'] and state['phase'] == 'Making_M',
                           HasPlayer=False, Config=NS(ShowInMap=False), PlayerRef=None, CenterRef=None,
                           GetActiveScene=lambda: 'scene', STATE_PLAYING='Animating',
                           SexLabRegistry=NS(GetStripDataA=lambda *a: Array([1]),
                                             GetPositionSexA=lambda *a: Array([1])),
                           GoToState=lambda next_state: effects.append(next_state))

                def wait(delay):
                    waits.append(delay)
                    if len(waits) == cancel_at:
                        state.update(revision=6 if reuse else 5, phase=phase)
                        # Reuse in the same state must be rejected by revision.
                        if phase == 'Making_M':
                            state['revision'] = 6
                        env['_Positions'] = Array([object()]) if reuse else Array()
                        effects.append('cancel')

                env['Utility'] = NS(Wait=wait)
                method = 'UndressAndStripActorsForRevision' if 'Function UndressAndStripActorsForRevision(' in source('sslThreadModel') else 'UndressAndStripActors'
                call('sslThreadModel', method, env)
                if cancel_at is None:
                    self.assertEqual(effects, ['ready', 'Animating'])
                else:
                    self.assertEqual(effects[effects.index('cancel') + 1:], [])

    def test_alias_path_wait_stops_after_cancel_or_actor_reuse(self):
        for cancel_at in (None, 1, 2):
            with self.subTest(cancel_at=cancel_at):
                effects, waits, distances = [], [], [20, 15, 9]
                state = dict(revision=4, phase='Ready', actor=None)

                def distance(_):
                    effects.append('distance')
                    return distances.pop(0) if distances else 9

                actor = NS(GetDistance=distance, SetFactionRank=lambda *a: effects.append('faction'))
                state['actor'] = actor
                thread = NS(SetupRevision=4, CalcPathingTargetDistance=lambda _: 10,
                            UpdateAnimatingActorMovement=lambda _: effects.append('unlock'))
                env = dict(_Thread=thread, _ActorRef=actor, _PlayerRef=object(), _raceID=0,
                           aiRevision=4, akPrepareActor=actor,
                           _AnimatingFaction=object(), DoPathToCenter=True, akPathTo=object(),
                           STATE_SETUP='Ready', GetState=lambda: state['phase'],
                           _Config=NS(CheckBardAudience=lambda *a: None), Math=NS(abs=abs))
                env['IsCurrentAliasPreparation'] = lambda rev, old_actor, phase: (
                    rev == state['revision'] and old_actor is state['actor'] and state['phase'] == phase)

                def wait(delay):
                    waits.append(delay)
                    if len(waits) == cancel_at:
                        state.update(revision=5, phase='Ready', actor=object())
                        env['_ActorRef'] = NS(GetDistance=lambda _: self.fail('stale path touched replacement actor'))
                        effects.append('cancel')

                env['Utility'] = NS(Wait=wait)
                name = 'WaitForPathToCenterForRevision' if 'Function WaitForPathToCenterForRevision(' in source('sslActorAlias') else 'WaitForPathToCenter'
                call('sslActorAlias', name, env)
                if cancel_at is None:
                    self.assertEqual(waits, [2.0, .05, .05])
                else:
                    self.assertEqual(effects[effects.index('cancel') + 1:], [])

    def test_alias_event_never_pauses_or_notifies_reused_session(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                effects, state = [], dict(revision=9, phase='Ready', actor=None)
                actor = NS(GetAnimationVariableInt=lambda _: 1, GetAnimationVariableBool=lambda _: False)
                state['actor'] = actor
                thread = NS(SetupRevision=9, tid='2', PrepareDone=lambda: effects.append('unguarded notify'),
                            PrepareDoneForRevision=lambda rev: effects.append(('notify', rev)))
                env = dict(_Thread=thread, _ActorRef=actor, STATE_SETUP='Ready', STATE_PAUSED='Paused',
                           _sex=0, _Config=NS(MaleVoiceDelay=5, DebugMode=False),
                           asEventName='SSL_PREPARE_Thread2', asStringArg='9', afNumArg=0,
                           akPathTo=object(), UnregisterForModEvent=lambda _: None)

                def path(_):
                    if cancelled:
                        state.update(revision=10, phase='Ready', actor=object())
                        env['_ActorRef'] = NS(GetAnimationVariableInt=lambda _: self.fail('old event read reused actor'))

                def change(phase):
                    state['phase'] = phase
                    effects.append(('state', phase))

                env.update(WaitForPathToCenter=path,
                    WaitForPathToCenterForRevision=lambda target, revision, original: path(target), GoToState=change,
                    IsCurrentAliasPreparation=lambda rev, old_actor, phase: (
                        rev == state['revision'] and old_actor is state['actor'] and state['phase'] == phase))
                event('sslActorAlias', 'OnDoPrepare', env)
                self.assertEqual(effects, [] if cancelled else [('state', 'Paused'), ('notify', 9)])

    def test_old_prepare_event_rejected_before_new_registration_is_removed(self):
        for token, expected in (('8', []), ('9', ['unregister', 'path', ('state', 'Paused'), ('notify', 9)]),
                                ('skip', ['unregister', 'path', ('state', 'Paused')])):
            with self.subTest(token=token):
                effects, state = [], {'phase': 'Ready'}
                actor = NS(GetAnimationVariableInt=lambda _: 1, GetAnimationVariableBool=lambda _: False)
                thread = NS(SetupRevision=9, tid='2', PrepareDoneForRevision=lambda rev: effects.append(('notify', rev)))
                env = dict(_Thread=thread, _ActorRef=actor, STATE_SETUP='Ready', STATE_PAUSED='Paused',
                           _sex=0, _Config=NS(MaleVoiceDelay=5, DebugMode=False),
                           asEventName='SSL_PREPARE_Thread2', asStringArg=token, afNumArg=0,
                           akPathTo=object(), UnregisterForModEvent=lambda _: effects.append('unregister'),
                           WaitForPathToCenter=lambda _: effects.append('path'),
                           WaitForPathToCenterForRevision=lambda *a: effects.append('path'))
                env['IsCurrentAliasPreparation'] = lambda rev, original, phase: rev == 9 and original is actor and state['phase'] == phase

                def change(phase):
                    state['phase'] = phase
                    effects.append(('state', phase))

                env['GoToState'] = change
                event('sslActorAlias', 'OnDoPrepare', env)
                self.assertEqual(effects, expected)

    def test_alias_path_entry_carries_original_actor_and_revision(self):
        effects = []
        actor = object()
        replacement = NS(GetDistance=lambda _: self.fail('stale helper read replacement actor'))
        env = dict(_Thread=NS(SetupRevision=10), _ActorRef=replacement, _PlayerRef=replacement,
                   aiRevision=9, akPrepareActor=actor, akPathTo=object(), STATE_SETUP='Ready',
                   IsCurrentAliasPreparation=lambda revision, original, phase: revision == 10 and original is replacement,
                   Game=NS(DisablePlayerControls=lambda **kw: effects.append('disable')),
                   _Config=NS(HasVRIK=False, CheckBardAudience=lambda *a: effects.append('audience')))
        call('sslActorAlias', 'WaitForPathToCenterForRevision', env)
        self.assertEqual(effects, [])
        text = source('sslActorAlias')
        method = re.findall(r'(?ims)^\s*Event OnDoPrepare\([^\n]*\)\s*\n(.*?)^\s*EndEvent', text)[0]
        self.assertIn('WaitForPathToCenterForRevision(akPathTo, prepareRevision, prepareActor)', method)

    def test_prepared_count_rejects_stale_or_wrong_state(self):
        # Exercise the actual guard before any count increment/side effect.
        for current, phase in ((6, 'Making_M'), (7, 'Making_M'), (6, 'Ending')):
            with self.subTest(current=current, phase=phase):
                finished = []
                env = dict(aiRevision=6, _prepareAsyncCount=0, _Positions=Array([object()]),
                           IsCurrentPreparation=lambda rev: current == rev and phase == 'Making_M',
                           Log=lambda _: None, HasPlayer=False, FinishPreparation=lambda: finished.append(True))
                # First matching completion increments once, below the two-completion barrier.
                _, result = call('sslThreadModel', 'PrepareDoneForRevision', env)
                self.assertEqual(result['_prepareAsyncCount'], int(current == 6 and phase == 'Making_M'))
                self.assertEqual(finished, [])

    def test_preparation_internal_chain_does_not_recapture_revision(self):
        for method in ('FinishPreparationForRevision', 'UndressAndStripActorsForRevision'):
            with self.subTest(method=method):
                effects = []
                call('sslThreadModel', method, dict(aiRevision=4, SetupRevision=5,
                    IsCurrentPreparation=lambda revision: revision == 5,
                    GetActiveScene=lambda: effects.append('read-new-scene'),
                    UndressAndStripActorsForRevision=lambda rev: effects.append(('undress', rev))))
                self.assertEqual(effects, [])
        done = engine['body']('sslThreadModel', 'PrepareDoneForRevision')
        finish = engine['body']('sslThreadModel', 'FinishPreparationForRevision')
        self.assertIn('FinishPreparationForRevision(aiRevision)', done)
        self.assertIn('UndressAndStripActorsForRevision(aiRevision)', finish)

    def test_native_preparation_completion_queue_carries_origin(self):
        native = (ROOT / 'src/Thread/ThreadAnimation.cpp').read_text(encoding='utf-8-sig')
        for callback in ('OnPlayerDialogueComplete', 'OnNativeActorRecoveryComplete', 'OnPlayerSheatheComplete'):
            actual = re.search(r'"(' + callback + r'(?:ForRevision)?)"', native)[1]
            for revision, phase, succeeded in itertools.product((11, 12), ('Making_M', 'Ending'), (False, True)):
                with self.subTest(callback=callback, revision=revision, phase=phase, success=succeeded):
                    effects = []
                    state = dict(revision=revision, phase=phase)
                    env = dict(aiRevision=11, SetupRevision=revision, abSucceeded=succeeded, PlayerRef=object(),
                               IsCurrentPreparation=lambda rev: rev == state['revision'] and state['phase'] == 'Making_M',
                               BeginActorRecovery=lambda: effects.append('recover') or True,
                               EndAnimation=lambda: effects.append('end'),
                               ActorAlias=lambda _: NS(NativeActorLockApplied=lambda: effects.append('lock')))
                    # Legacy wrappers deliberately take the current revision;
                    # the actual native dispatcher must use the guarded entry.
                    env['BeginAliasPreparation'] = lambda: effects.append(('prepare', revision))
                    env['BeginAliasPreparationForRevision'] = lambda rev: effects.append(('prepare', rev))
                    env['FinishPreparation'] = lambda: effects.append(('finish', revision))
                    env['FinishPreparationForRevision'] = lambda rev: effects.append(('finish', rev))
                    call('sslThreadModel', actual, env)
                    if revision != 11 or phase != 'Making_M':
                        self.assertEqual(effects, [])
                    elif callback == 'OnPlayerDialogueComplete':
                        self.assertEqual(effects, ['recover', ('prepare', 11)])
                    elif not succeeded:
                        self.assertEqual(effects, ['end'])
                    elif callback == 'OnNativeActorRecoveryComplete':
                        self.assertEqual(effects, [('prepare', 11)])
                    else:
                        self.assertEqual(effects, ['lock', ('finish', 11)])
            self.assertEqual(actual, callback + 'ForRevision')
            dispatch = re.search(r'Script::DispatchMethodCall\([^;]*"' + actual + r'"[^;]*?\)\)', native)[0]
            self.assertIn('int{ setupRevision }', dispatch)

    def test_preparation_native_wait_reuse_cannot_continue(self):
        for callback, boundary in (('OnPlayerDialogueCompleteForRevision', 'recovery'),
                                   ('OnPlayerSheatheCompleteForRevision', 'alias-lookup'),
                                   ('OnPlayerSheatheCompleteForRevision', 'alias-lock')):
            with self.subTest(callback=callback, boundary=boundary):
                state, effects = {'revision': 11}, []
                def cancel():
                    state['revision'] = 12
                    effects.append('cancel')
                def recover():
                    cancel()
                    return True
                def mark_locked():
                    effects.append('lock')
                    if boundary == 'alias-lock':
                        cancel()
                def alias(_):
                    if boundary == 'alias-lookup':
                        cancel()
                    return NS(NativeActorLockApplied=mark_locked)
                env = dict(aiRevision=11, abSucceeded=True, PlayerRef=object(),
                           IsCurrentPreparation=lambda rev: rev == state['revision'],
                           BeginActorRecovery=recover, ActorAlias=alias,
                           EndAnimation=lambda: effects.append('end'),
                           BeginAliasPreparationForRevision=lambda rev: effects.append('prepare'),
                           FinishPreparationForRevision=lambda rev: effects.append('finish'))
                call('sslThreadModel', callback, env)
                self.assertEqual(effects[effects.index('cancel') + 1:], [])

    def test_preparation_on_begin_state_keeps_its_revision(self):
        state_body = source('sslThreadModel').split('State Making_M', 1)[1].split('EndState', 1)[0]
        begin = re.search(r'(?ims)Event OnBeginState\(\)\s*\n(.*?)^\s*EndEvent', state_body)[1]
        for boundary in ('none', 'dialogue', 'recovery'):
            with self.subTest(boundary=boundary):
                effects, state = [], {'revision': 5}
                def wait(kind):
                    effects.append(kind)
                    if boundary == kind:
                        state['revision'] = 6
                        effects.append('cancel')
                    return True
                env = dict(SetupRevision=5, IsCurrentPreparation=lambda rev: rev == state['revision'],
                           BeginPlayerDialogueWait=lambda: wait('dialogue'),
                           BeginActorRecovery=lambda: wait('recovery'),
                           BeginAliasPreparation=lambda: effects.append(('prepare', state['revision'])),
                           BeginAliasPreparationForRevision=lambda rev: effects.append(('prepare', rev)))
                engine['execute'](without_diagnostics(begin), env)
                if boundary == 'none':
                    self.assertEqual(effects, ['dialogue', 'recovery', ('prepare', 5)])
                else:
                    self.assertEqual(effects[effects.index('cancel') + 1:], [])

    def test_preparation_callback_defaults_and_helper_entry_reject_stale(self):
        for callback in ('OnPlayerDialogueCompleteForRevision', 'OnNativeActorRecoveryCompleteForRevision',
                         'OnPlayerSheatheCompleteForRevision', 'BeginAliasPreparationForRevision'):
            with self.subTest(callback=callback):
                effects = []
                env = dict(aiRevision=11, abSucceeded=True, SetupRevision=12,
                           IsCurrentPreparation=lambda _: False, _prepareAsyncCount=9,
                           BeginAliasPreparationForRevision=lambda rev: effects.append('prepare'),
                           FinishPreparationForRevision=lambda rev: effects.append('finish'),
                           CenterRef=NS(SendModEvent=lambda *args: effects.append('event')))
                call('sslThreadModel', callback, env)
                self.assertEqual(effects, [])
                self.assertEqual(env['_prepareAsyncCount'], 9)
                call('sslThreadModel', callback, env, 1)  # default state is inert
                self.assertEqual(effects, [])
                self.assertEqual(env['_prepareAsyncCount'], 9)

    def test_alias_barrier_has_tags_before_immediate_completion(self):
        for cancel_on in (None, 'get-custom', 'get-tags'):
            with self.subTest(cancel_on=cancel_on):
                state, completions = {'revision': 3}, []
                env = dict(SetupRevision=3, aiRevision=3, tid='0', _prepareAsyncCount=0,
                           _ThreadTags=Array(['original']), _LeadInScenes=Array(),
                           _PrimaryScenes=Array(), _CustomScenes=Array(),
                           IsCurrentPreparation=lambda rev: state['revision'] == rev,
                           CenterRef=NS(SendModEvent=lambda event, token: self.assertEqual(token, '3')),
                           GetLeadInScenes=lambda: Array(), GetPrimaryScenes=lambda: Array(['primary']),
                           SortAliasesToPositions=lambda: None)

                def customs():
                    if cancel_on == 'get-custom':
                        state['revision'] += 1
                    return Array()

                def tags(_):
                    if cancel_on == 'get-tags':
                        state['revision'] += 1
                    return Array(['tag'])

                def complete(revision):
                    completions.append((revision, list(env['_ThreadTags'])))
                    # All other aliases already acknowledged; continuation can
                    # synchronously reach Animating before returning here.
                    state['revision'] += 1

                env.update(GetCustomScenes=customs, SexLabRegistry=NS(GetCommonTags=tags),
                           PrepareDoneForRevision=complete, PrepareDone=lambda: complete(3))
                name = 'BeginAliasPreparationForRevision' if 'Function BeginAliasPreparationForRevision(' in source('sslThreadModel') else 'BeginAliasPreparation'
                call('sslThreadModel', name, env)
                if cancel_on is None:
                    self.assertEqual(completions, [(3, ['tag'])])
                else:
                    self.assertEqual(completions, [])
                    self.assertEqual(env['_ThreadTags'], ['original'])

    def test_branch_callback_requires_original_session_scene_and_stage(self):
        for current_rev, scene, stage in itertools.product((11, 12), ('scene', 'changed'), ('stage', 'changed')):
            with self.subTest(revision=current_rev, scene=scene, stage=stage):
                calls = []
                call('sslThreadController', 'BranchToForRevision', dict(
                    aiChoice=1, aiRevision=11, asSceneId='scene', asStageId='stage',
                    IsCurrentPlayback=lambda rev: rev == current_rev,
                    GetActiveScene=lambda: scene, GetActiveStage=lambda: stage,
                    BranchTo=calls.append))
                self.assertEqual(calls, [1] if (current_rev, scene, stage) == (11, 'scene', 'stage') else [])

    def test_graph_callback_rejects_reuse_before_and_during_close(self):
        for changed in ('none', 'before-delivery', 'during-close'):
            with self.subTest(changed=changed):
                state, calls = {'revision': 11 if changed != 'before-delivery' else 12}, []
                env = dict(asTarget='next', aiRevision=11, asSceneId='scene', asStageId='stage',
                           IsCurrentPlayback=lambda rev: rev == state['revision'],
                           GetActiveScene=lambda: 'scene', GetActiveStage=lambda: 'stage',
                           SkipTo=lambda target: calls.append(('skip', target)))

                def close(force):
                    calls.append(('close', force))
                    if changed == 'during-close':
                        state['revision'] += 1

                env['ToggleVisibilitySceneGraph'] = close
                env['CloseGraphForRevision'] = lambda rev: call('sslThreadController', 'CloseGraphForRevision', dict(env, aiRevision=rev))
                call('sslThreadController', 'SkipToFromGraphForRevision', env)
                expected = [] if changed == 'before-delivery' else [('close', -1)]
                if changed == 'none':
                    expected.append(('skip', 'next'))
                self.assertEqual(calls, expected)

    def test_lovense_duration_uses_float_setting(self):
        text = source('sslActorAlias')
        self.assertIn('float duration = sslSystemConfig.GetSettingFlt("fLovenseDurationOrgasm")', text)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
