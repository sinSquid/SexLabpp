"""Run extracted startup PSC paths and compile the real assignment algorithm.

No Skyrim/Papyrus VM or full Mod build. --baseline-ref HEAD exercises the same
arrival and duplicate-sync cases against the pre-change scripts. The native
harness adapts the old signature only, so its exhaustive work remains visible.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import itertools
import os
import subprocess
import tempfile
import unittest

import full_review_papyrus_1111 as psc

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    if psc.args.baseline_ref:
        return subprocess.check_output(['git', 'show', psc.args.baseline_ref + ':' + path], cwd=ROOT).decode('utf-8-sig')
    return (ROOT / path).read_text(encoding='utf-8-sig')


def cpp_function(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class StartupRegressions(unittest.TestCase):
    def path(self, distance_at, cancel_at=None, enabled=True, wake_overrun=0.0, menu_pause=0.0,
             clock_reuse_at=None, invalid_clock_at=None):
        clock, effects = [0.0], []
        wall_clock = [0.0]
        state = dict(revision=4, current=True)
        clock_reads = []

        def preparation_clock(revision):
            clock_reads.append(1)
            if len(clock_reads) == clock_reuse_at:
                state.update(revision=5, current=False)
                effects.append(('cancel', clock[0]))
                return clock[0]  # A valid old snapshot returned after reuse.
            if len(clock_reads) == invalid_clock_at:
                effects.append(('invalid-clock', clock[0]))
                return -1
            return clock[0] if state['current'] and revision == state['revision'] else -1

        def distance(_):
            self.assertTrue(state['current'], 'stale preparation touched an actor')
            effects.append(('distance', clock[0]))
            return distance_at(clock[0])

        actor = NS(GetDistance=distance, SetFactionRank=lambda *a: effects.append(('faction', 0)))
        thread = NS(CalcPathingTargetDistance=lambda _: 10,
                    UpdateAnimatingActorMovement=lambda _: effects.append(('unlock', 0)),
                    GetPreparationElapsedTime=preparation_clock)
        env = dict(aiRevision=4, akPrepareActor=actor, _ActorRef=actor, _PlayerRef=object(),
                   _Thread=thread, _raceID=0, _AnimatingFaction=object(), DoPathToCenter=enabled,
                   akPathTo=object(), STATE_SETUP='Ready',
                   _Config=NS(CheckBardAudience=lambda *a: None), Math=NS(abs=abs),
                   IsCurrentAliasPreparation=lambda rev, ref, phase: state['current'] and rev == state['revision'])

        def wait(delay):
            clock[0] += delay + wake_overrun
            wall_clock[0] += delay + wake_overrun
            if menu_pause:
                wall_clock[0] += menu_pause
            self.assertLess(clock[0], 18, 'path wait exceeded original nominal budget')
            if cancel_at is not None and clock[0] >= cancel_at:
                state.update(revision=5, current=False)
                env['_ActorRef'] = NS(GetDistance=lambda _: self.fail('replacement actor was accessed'))
                effects.append(('cancel', clock[0]))

        env['Utility'] = NS(Wait=wait, GetCurrentRealTime=lambda: wall_clock[0])
        psc.call('sslActorAlias', 'WaitForPathToCenterForRevision', env)
        if not state['current']:
            self.assertEqual(effects[effects.index(next(e for e in effects if e[0] == 'cancel')) + 1:], [])
        return clock[0], effects

    def test_arrival_before_two_seconds_finishes_promptly(self):
        for arrival in (.05, .3, .9, 1.5, 1.95):
            with self.subTest(arrival=arrival):
                elapsed, _ = self.path(lambda t: 20 if t < arrival else 9)
                self.assertLessEqual(elapsed, arrival + .101)

    def test_no_path_needed_does_not_wait_or_unlock(self):
        for distance, enabled in ((9, True), (10, True), (7000, True), (20, False)):
            elapsed, effects = self.path(lambda _: distance, enabled=enabled)
            self.assertEqual(elapsed, 0)
            self.assertNotIn(('unlock', 0), effects)

    def test_late_package_start_keeps_grace_and_longer_walks_can_finish(self):
        elapsed, _ = self.path(lambda t: 50 if t < 1.9 else max(9, 50 - 20 * (t - 1.9)))
        self.assertGreater(elapsed, 2)
        self.assertLess(elapsed, 4.1)

    def test_stalled_and_slow_walks_remain_bounded(self):
        elapsed, _ = self.path(lambda _: 20)
        self.assertAlmostEqual(elapsed, 2.05)
        elapsed, _ = self.path(lambda t: 1000 - 20 * t)
        self.assertGreaterEqual(elapsed, 16.9)
        self.assertLessEqual(elapsed, 17.1)

    def test_grace_deadline_includes_wakeup_overrun_and_excludes_menus(self):
        for overrun in (.05, .15, .25):
            for pause in (0, 60):
                with self.subTest(overrun=overrun, pause=pause):
                    elapsed, _ = self.path(lambda _: 20, wake_overrun=overrun, menu_pause=pause)
                    self.assertGreaterEqual(elapsed, 2)
                    # One last grace wake and the unchanged stall check can overrun.
                    self.assertLessEqual(elapsed, 2.15 + 2 * overrun)

    def test_path_clock_return_cannot_continue_cancelled_preparation(self):
        for boundary in (1, 2, 3):
            with self.subTest(boundary=boundary):
                _, effects = self.path(lambda _: 20, clock_reuse_at=boundary)
                self.assertEqual(effects[-1][0], 'cancel')
                _, effects = self.path(lambda _: 20, invalid_clock_at=boundary)
                self.assertEqual(effects[-1][0], 'invalid-clock')

    def test_native_preparation_clock_uses_locked_unpaused_unscaled_frames(self):
        update = cpp_function(read('src/Thread/ThreadAnimation.cpp'), 'void Instance::UpdateAnimations(')
        self.assertIn('const bool paused = Util::IsGamePausedOrFrozen();', update)
        self.assertIn('preparationDelta = paused ? 0.0f : std::max(0.0f, RE::BSTimer::GetSingleton()->realTimeDelta)', update)
        self.assertLess(update.index('LockState()'), update.index('instance->preparationElapsed += preparationDelta'))
        self.assertIn('a_revision == setupRevision ? static_cast<float>(preparationElapsed) : -1.0f', read('src/Thread/Thread.h'))
        native = cpp_function(read('src/Papyrus/sslThreadModel.cpp'), 'float GetPreparationElapsedTime(')
        self.assertIn('GET_INSTANCE(-1.0f)', native)
        self.assertIn('instance->GetPreparationElapsedTime(a_revision)', native)
        self.assertIn('REGISTERFUNC(GetPreparationElapsedTime, "sslThreadModel", true)', read('src/Papyrus/sslThreadModel.h'))

    def test_cancellation_and_reuse_at_every_wait_boundary(self):
        for cancel_at in (.01, .15, .95, 1.95, 2.01, 2.5, 8, 16.9):
            with self.subTest(cancel_at=cancel_at):
                elapsed, effects = self.path(lambda t: 1000 - 20 * t, cancel_at=cancel_at)
                self.assertTrue(any(kind == 'cancel' for kind, _ in effects))
                self.assertLessEqual(elapsed, cancel_at + .101)

    def test_legacy_name_and_registrar_sync_once_and_keep_bounds(self):
        for method, argument in (('GetByName', 'FindName'), ('GetbyRegistrar', 'Registrar'), ('GetBySlot', 'index')):
            for index in (-1, 0, 1, 2):
                with self.subTest(method=method, index=index):
                    syncs = []
                    aliases = psc.Array([object(), object()])
                    env = dict(GetAliases=lambda: aliases, index=index,
                               SyncBackEnd=lambda: syncs.append('sync'),
                               FindName='requested', Registrar='requested')

                    def find(_):
                        env['SyncBackEnd']()
                        return index

                    env.update(FindByName=find, FindByRegistrar=find,
                               GetBySlot=lambda i: psc.call('sslAnimationSlots', 'GetBySlot', dict(env, index=i))[0],
                               GetBySlotSynced=lambda i: psc.call('sslAnimationSlots', 'GetBySlotSynced', dict(env, index=i))[0])
                    result, _ = psc.call('sslAnimationSlots', method, dict(env, **{argument: index if argument == 'index' else 'requested'}))
                    self.assertIs(result, aliases[index] if 0 <= index < len(aliases) else None)
                    self.assertEqual(syncs, ['sync'])

    def test_timing_is_debug_only_and_rejects_old_revision(self):
        self.assertIn('Function TraceStartupPhase(', psc.source('sslThreadModel'))
        for debug, revision, stored in itertools.product((False, True), (4, 5), (4, 5)):
            logs = []
            env = dict(_startupTimingEnabled=debug, aiRevision=revision, _startupTimingRevision=stored,
                       SetupRevision=5, _startupStartedAt=10, asPhase='prepare-ready',
                       Utility=NS(GetCurrentRealTime=lambda: 12.5), LogStartupTiming=lambda *a: logs.append(a))
            psc.call('sslThreadModel', 'TraceStartupPhase', env)
            self.assertEqual(logs, [('prepare-ready', 5, 2.5)] if debug and revision == stored == 5 else [])
        header = read('src/Papyrus/sslThreadModel.h')
        self.assertIn('REGISTERFUNC(LogStartupTiming, "sslThreadModel", true)', header)
        script = psc.source('sslThreadModel')
        self.assertIn('Config.DebugMode', script)
        for phase in ('native-request', 'native-ready', 'prepare-begin', 'prepare-ready',
                      'equipment-begin', 'equipment-ready', 'aliases-ready', 'playback-started'):
            self.assertIn('TraceStartupPhase("' + phase + '"', script)

    def test_startup_diagnostics_cannot_overwrite_reused_completion(self):
        for debug, boundary in ((False, 'config'), (True, 'config'), (True, 'clock'), (False, 'state')):
            with self.subTest(debug=debug, boundary=boundary):
                effects = []
                env = dict(SetupRevision=10, _Positions=psc.Array([object()]), POSITION_COUNT_MAX=5,
                           LeadIn=True, _QuickResetScenes=False, _PrimaryScenes=psc.Array(['scene']),
                           _LeadInScenes=psc.Array(), _CustomScenes=psc.Array(), _furniStatus=1,
                           STATE_SETUP='Making', STATE_SETUP_M='Making_M',
                           UnregisterForUpdate=lambda: effects.append('unregister'),
                           RunHook=lambda *a: effects.append('hook'), GetSubmissives=lambda: psc.Array(),
                           TraceStartupPhase=lambda *a: None, CreateInstanceForRevision=lambda *a: None,
                           PapyrusUtil=NS(RemoveActor=lambda a, _: a),
                           _startupTimingEnabled=False, _startupStartedAt=17, _startupTimingRevision=13)

                def reuse(where):
                    if where == boundary:
                        env.update(SetupRevision=13, _instanceCreationWaitLock=1,
                                   _startupTimingEnabled=False, _startupStartedAt=17, _startupTimingRevision=13)
                        effects.append('reuse')

                class Config:
                    HOOKID_STARTING = 0

                    @property
                    def DebugMode(self):
                        reuse('config')
                        return debug

                def now():
                    reuse('clock')
                    return 99

                def state():
                    reuse('state')
                    return 'Making'

                env.update(Config=Config(), Utility=NS(GetCurrentRealTime=now), GetState=state)
                result, _ = psc.call('sslThreadModel', 'StartThread', env)
                self.assertIsNone(result)
                self.assertEqual(effects, ['reuse'])
                self.assertEqual(env['_instanceCreationWaitLock'], 1)
                self.assertFalse(env['_startupTimingEnabled'])
                self.assertEqual(env['_startupStartedAt'], 17)
                self.assertEqual(env['_startupTimingRevision'], 13)

    def test_native_ready_state_read_cannot_advance_reused_thread(self):
        for debug, replacement_state, signal in itertools.product(
                (False, True), (None, 'Making', 'Making_M', 'Ending'), (-1, 0, 1)):
            with self.subTest(debug=debug, state=replacement_state, signal=signal):
                effects, state_calls = [], []
                model = object()
                env = dict(SetupRevision=10, _Positions=psc.Array([object()]), POSITION_COUNT_MAX=5,
                           LeadIn=True, _QuickResetScenes=False, _PrimaryScenes=psc.Array(['scene']),
                           _LeadInScenes=psc.Array(), _CustomScenes=psc.Array(), _furniStatus=1,
                           STATE_SETUP='Making', STATE_SETUP_M='Making_M', self=model,
                           Config=NS(DebugMode=debug, HOOKID_STARTING=0),
                           UnregisterForUpdate=lambda: None, RunHook=lambda *a: None,
                           GetSubmissives=lambda: psc.Array(),
                           PapyrusUtil=NS(RemoveActor=lambda a, _: a),
                           Utility=NS(GetCurrentRealTime=lambda: 42, Wait=lambda _: self.fail('unexpected wait')),
                           GoToState=lambda state: effects.append(('transition', state)))

                def state():
                    state_calls.append(1)
                    if len(state_calls) == 3 and replacement_state is not None:
                        env.update(SetupRevision=13, _instanceCreationWaitLock=signal)
                        effects.append(('reuse', replacement_state))
                        return replacement_state
                    return 'Making'

                def create(*_):
                    env['_instanceCreationWaitLock'] = 1

                env.update(GetState=state, CreateInstanceForRevision=create)
                result, _ = psc.call('sslThreadModel', 'StartThread', env)
                self.assertEqual(len(state_calls), 3, 'test did not reach native-ready state read')
                if replacement_state is None:
                    self.assertIs(result, model)
                    self.assertEqual(effects, [('transition', 'Making_M')])
                else:
                    self.assertIsNone(result)
                    self.assertEqual(effects, [('reuse', replacement_state)])
                    self.assertEqual(env['_instanceCreationWaitLock'], signal)

    def test_timing_call_cancellation_cannot_advance_reused_thread(self):
        for method, phase in (
                ('StartThread', 'native-ready'),
                ('BeginAliasPreparationForRevision', 'prepare-begin'),
                ('PrepareDoneForRevision', 'prepare-ready'),
                ('FinishPreparationForRevision', 'equipment-begin'),
                ('UndressAndStripActorsForRevision', 'equipment-ready'),
                ('AnimationStart', 'aliases-ready'),
                ('OnAnimationSynchronized', 'playback-started')):
            with self.subTest(phase=phase):
                state, effects = dict(current=True), []
                env = dict(aiRevision=4, SetupRevision=4, PlaybackRevision=9,
                           _Positions=psc.Array(), ActorAlias=psc.Array(), HasPlayer=False,
                           IsCurrentPreparation=lambda _: state['current'],
                           IsCurrentPlayback=lambda _: state['current'], _prepareAsyncCount=0,
                           Config=NS(ShowInMap=False, DebugMode=False, HOOKID_STARTING=0),
                           GetActiveScene=lambda: 'scene',
                           SexLabRegistry=NS(GetStripDataA=lambda *a: psc.Array(), GetPositionSexA=lambda *a: psc.Array()),
                           GoToState=lambda value: effects.append(('state', value)), STATE_PLAYING='Animating',
                           _animationSyncCount=0, _animationSyncPending=False, _animationStarted=False,
                           _sceneResetSyncPending=False, _queuedSceneReset='',
                           OnStageChangedUpdateHUD=lambda: None, ConfigureStageTimer=lambda _: None,
                           SendThreadEvent=lambda value: effects.append(('event', value)),
                           LeadIn=True, _QuickResetScenes=False, _PrimaryScenes=psc.Array(['scene']),
                           _LeadInScenes=psc.Array(), _CustomScenes=psc.Array(), _furniStatus=1,
                           UnregisterForUpdate=lambda: None, PapyrusUtil=NS(RemoveActor=lambda a, _: a),
                           RunHook=lambda _: None, GetSubmissives=lambda: psc.Array(),
                           GetState=lambda: 'Making' if state['current'] else 'Ending',
                           STATE_SETUP='Making', STATE_SETUP_M='Making_M', POSITION_COUNT_MAX=5,
                           Utility=NS(Wait=lambda _: self.fail('unexpected wait')))

                def create(*_):
                    env['_instanceCreationWaitLock'] = 1

                def probe(observed_phase, _):
                    if observed_phase == phase:
                        state['current'] = False
                        effects.append(('cancel', phase))
                        env.update(SetupRevision=99, PlaybackRevision=99, _animationStarted=False)

                env.update(CreateInstanceForRevision=create, ObserveStartupPhase=probe)
                if method == 'StartThread':
                    env['_Positions'] = psc.Array([object()])
                code = psc.engine['body']('sslThreadModel', method).replace('TraceStartupPhase(', 'ObserveStartupPhase(')
                psc.engine['execute'](psc.without_diagnostics(code).replace('prepareRevision as string', 'str(prepareRevision)'), env)
                self.assertFalse(state['current'], 'test did not reach the timing boundary')
                self.assertEqual(effects, [('cancel', phase)])
                if method == 'OnAnimationSynchronized':
                    self.assertFalse(env['_animationStarted'])

    def test_native_first_match_preserves_full_matches_and_scores(self):
        function = cpp_function(read('src/Registry/Define/Animation.cpp'),
                                'std::vector<std::vector<RE::Actor*>> Scene::FindAssignments(')
        # Adapt the baseline's signature without changing its exhaustive body.
        function = function.replace('a_fragments) const', 'a_fragments, bool a_firstOnly) const')
        code = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <numeric>
#include <set>
#include <utility>
#include <vector>
namespace RE { struct Actor { int id; }; }
static size_t actorReads = 0;
struct ActorFragment { RE::Actor* actor; RE::Actor* GetActor() const { ++actorReads; return actor; } };
struct Data {
    std::vector<int32_t> scores;
    int32_t GetCompatibilityScore(const ActorFragment& f) const { return scores[f.actor->id]; }
};
struct Position { Data data; };
struct Scene {
    std::vector<Position> positions;
    std::vector<std::vector<RE::Actor*>> FindAssignments(const std::vector<ActorFragment>&, bool = false) const;
};
''' + function + r'''
void check(Scene& scene, const std::vector<ActorFragment>& fragments) {
    const auto full = scene.FindAssignments(fragments);
    actorReads = 0;
    const auto first = scene.FindAssignments(fragments, true);
    assert(first.size() <= 1 && first.empty() == full.empty());
    assert(actorReads <= fragments.size()); // No materialization of all permutations.
    if (!first.empty()) assert(std::find(full.begin(), full.end(), first.front()) != full.end());
    std::vector<int> order(fragments.size());
    std::iota(order.begin(), order.end(), 0);
    std::set<std::vector<RE::Actor*>> expected;
    if (scene.positions.size() == fragments.size()) do {
        std::vector<RE::Actor*> actors(fragments.size());
        bool valid = true;
        for (size_t i = 0; i < order.size(); ++i) {
            if (!scene.positions[order[i]].data.GetCompatibilityScore(fragments[i])) valid = false;
            actors[order[i]] = fragments[i].actor;
        }
        if (valid) expected.insert(actors);
    } while (std::next_permutation(order.begin(), order.end()));
    assert((std::set<std::vector<RE::Actor*>>(full.begin(), full.end()) == expected));
    int32_t previous = INT32_MAX;
    for (const auto& assignment : full) {
        int32_t score = 0;
        for (size_t i = 0; i < assignment.size(); ++i) score += scene.positions[i].data.scores[assignment[i]->id];
        assert(score <= previous);
        previous = score;
    }
}
int main() {
    std::vector<RE::Actor> actors(5);
    std::vector<ActorFragment> fragments;
    for (int i = 0; i < 5; ++i) { actors[i].id = i; fragments.push_back({ &actors[i] }); }
    Scene scene;
    for (unsigned bits = 0; bits < 512; ++bits) {
        scene.positions.assign(3, {});
        for (unsigned p = 0; p < 3; ++p) {
            scene.positions[p].data.scores.resize(5);
            for (unsigned a = 0; a < 3; ++a)
                scene.positions[p].data.scores[a] = bits & (1u << (p * 3 + a)) ? int32_t(p + 2 * a + 1) : 0;
        }
        check(scene, {fragments.begin(), fragments.begin() + 3});
    }
    for (size_t n = 0; n <= 5; ++n) {
        scene.positions.assign(n, {});
        for (size_t p = 0; p < n; ++p) {
            scene.positions[p].data.scores.resize(5);
            for (size_t a = 0; a < 5; ++a) scene.positions[p].data.scores[a] = int32_t((p + 1) * (a + 1));
        }
        check(scene, {fragments.begin(), fragments.begin() + n});
    }
    scene.positions[0].data.scores[0] = -1;
    check(scene, fragments);
    check(scene, {fragments.begin(), fragments.begin() + 2});
}
'''
        with tempfile.TemporaryDirectory(prefix='startup-matching-') as tmp:
            path = Path(tmp)
            source, binary = path / 'matching.cpp', path / 'matching.exe'
            source.write_text(code, encoding='utf-8')
            compiler = os.environ.get('CXX', 'cl')
            command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/W4', '/WX', str(source), '/Fe:' + str(binary)]
            if psc.args.baseline_ref:
                command.insert(1, '/wd4100')  # Baseline signature adapter adds an unused flag.
            result = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(binary)], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ctor = read('src/Thread/ThreadCtor.cpp')
        self.assertIn('FindAssignments(fragments, true)', ctor)
        registry = read('src/Papyrus/SexLabRegistry.cpp')
        self.assertIn('if (scene->FindAssignments(fragments, true).empty())', registry)
        # Score-sensitive selection still requests all assignments.
        self.assertIn('const auto ret = scene->FindAssignments(fragments);', registry)
        self.assertIn('a_scene->FindAssignments(fragments);', read('src/Thread/Thread.cpp'))


if __name__ == '__main__':
    unittest.main(argv=['startup regressions'], verbosity=2)
