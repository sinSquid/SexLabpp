"""No-compiler regressions for the 2026-11-10 review fixes.

Runs extracted production PSC bodies and a bounded surface gate with a Python
manager stand-in. Other native cases check source contracts only; none execute
C++ or validate its memory model, the Papyrus VM or game scheduling.
--baseline-dir accepts the saved pre-fix tree to demonstrate red cases.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse
import re
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-dir', type=Path)
args = parser.parse_args()
SOURCE = args.baseline_dir or ROOT


def read(path):
    return (SOURCE / path).read_text(encoding='utf-8-sig')


def cpp_body(path, signature):
    text = read(path)
    start = text.index(signature)
    start = text.index('{', start)
    end, depth = start + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


# Reuse the existing bounded PSC interpreter without running its test driver.
interpreter = (ROOT / 'tests/papyrus_confirmed_regressions.py').read_text(encoding='utf-8')
engine = {'__file__': str(ROOT / 'tests/papyrus_confirmed_regressions.py')}
saved_argv = sys.argv
try:
    sys.argv = [saved_argv[0]]
    # Keep the execution scope observable so a mocked latent Wait/native call
    # can deliver cancellation between two real production statements.
    prefix = interpreter[:interpreter.index('\nutility = NS(')].replace('scope = dict(env)', 'scope = env')
    exec(prefix, engine)
finally:
    sys.argv = saved_argv
engine['source'] = lambda name: read(f'dist/Source/Scripts/{name}.psc')


def psc(name, function, env, occurrence=0):
    return engine['execute'](engine['body'](name, function, occurrence), env)


def surface_control(signature, env):
    """Execute just the production surface gate/call with a manager stand-in.

    This bounded adapter understands if/call statements, not C++ or its memory
    model; the manager below supplies the registration/unregistration barrier.
    """
    body = cpp_body('src/Thread/Thread.h', signature)[1:-1]
    output, indent = [], 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == '}':
            indent -= 1
            continue
        line = line.replace('::', '.').replace('->', '.').replace('false', 'False')
        if line.startswith('if (') and line.endswith(') {'):
            output.append('    ' * indent + 'if ' + line[4:-3] + ':')
            indent += 1
        else:
            assert line.endswith(';'), line
            output.append('    ' * indent + line[:-1])
    assert indent == 0
    exec(compile('\n'.join(output), 'extracted surface control', 'exec'), env)


# Reuse the actual MCM/control bodies and registration stand-ins, without the
# optional C++ executable or the old test driver's mutations of the fixture.
hotkey_test = (ROOT / 'tests/scene_select_hotkey.py').read_text(encoding='utf-8')
hotkeys = dict(ROOT=ROOT, re=re, SimpleNamespace=SimpleNamespace,
               controller=read('dist/Source/Scripts/sslThreadController.psc'),
               menu=read('dist/Source/Scripts/sslConfigMenu.psc'),
               system=read('dist/Source/Scripts/sslSystemConfig.psc'))
exec(hotkey_test[hotkey_test.index('class Returned('):
                  hotkey_test.index('# Execute actual control bodies')], hotkeys)


class ReviewRegressions(unittest.TestCase):
    def test_shared_main_rebind_and_unbind(self):
        for modifier in (29, 42):
            for new_key in (50, -1):
                with self.subTest(modifier=modifier, new_key=new_key):
                    e, _, _, settings = hotkeys['fixture']()
                    settings.update(iOpenSceneSelect=49, iSceneSelectModifier=modifier,
                                    iTargetActor=49, iToggleFreeCamera=81, iToggleThreadControl=21)
                    # Production global properties read the updated settings.
                    e['Config'].IsGlobalHotkey = lambda key: key in (
                        settings['iTargetActor'], settings['iToggleFreeCamera'], settings['iToggleThreadControl'])
                    e['RegisterHotkeys']()
                    e.update(GetState=lambda: 'R_iTargetActor', newKeyCode=new_key)
                    e['OnKeyMapChangeST']()
                    self.assertIn(49, e['configKeys'])
                    self.assertEqual(settings['iTargetActor'], new_key)
                    if new_key >= 0:
                        self.assertIn(new_key, e['configKeys'])

    def test_rebind_preserves_other_global_owner(self):
        e, _, _, settings = hotkeys['fixture']()
        settings.update(iTargetActor=49, iToggleFreeCamera=49, iToggleThreadControl=21)
        e['Config'].RegisterForKey(49)
        e['Config'].GetThreadControlled = lambda: None
        e['Config'].IsGlobalHotkey = lambda key: key in (
            settings['iTargetActor'], settings['iToggleFreeCamera'], settings['iToggleThreadControl'])
        e.update(GetState=lambda: 'R_iTargetActor', newKeyCode=50)
        e['OnKeyMapChangeST']()
        self.assertIn(49, e['configKeys'])

    def test_legacy_getters_return_arrays(self):
        text = read('dist/Source/Scripts/sslThreadModel.psc')
        for prop, expected, env in (
            ('Victims', [object()], {}), ('BedStatus', [1, 3], {'_furniStatus': 2, 'BedTypeID': 3})):
            with self.subTest(property=prop):
                match = re.search(r'(?is)\bproperty\s+' + prop + r'\s+Hidden\s*\n\s*\w+\[\]\s+Function\s+Get\(\)\s*\n(.*?)EndFunction', text)
                env['GetAllVictims'] = lambda: expected
                value, _ = engine['execute'](match[1], env)
                self.assertEqual(value, expected)

    def test_legacy_expression_phase_index(self):
        for phase in (1, 2, 8):
            with self.subTest(phase=phase):
                calls = []
                common = dict(Registry='profile', Phase=phase, Gender=1, Female=1, Preset=[.1],
                              GetNthValues=lambda *a: a[-1], SetValues=lambda *a: calls.append(a))
                result, _ = psc('sslBaseExpression', 'GenderPhase', common)
                self.assertEqual(result, phase - 1)
                psc('sslBaseExpression', 'SetPhase', dict(common, Gender=-1))
                self.assertEqual([(x[1], x[2]) for x in calls], [(True, phase - 1), (False, phase - 1)])

    def test_stale_setup_callback(self):
        # The Making-state override directly commits only its own revision.
        for current, received in ((4, 3), (4, 4), (5, 4)):
            with self.subTest(current=current, received=received):
                _, scope = psc('sslThreadModel', 'ContinueSetupForRevision',
                               dict(SetupRevision=current, aiRevision=received, abContinue=True,
                                    _instanceCreationWaitLock=-1))
                self.assertEqual(scope['_instanceCreationWaitLock'], 1 if current == received else -1)
        # Idle/default must never release a newer setup's wait.
        _, scope = psc('sslThreadModel', 'ContinueSetupForRevision',
                       dict(SetupRevision=4, aiRevision=4, abContinue=True,
                            _instanceCreationWaitLock=-1), 1)
        self.assertEqual(scope['_instanceCreationWaitLock'], -1)

    def test_start_wait_cancellation_and_success(self):
        for mode in ('normal', 'cancel_at_create', 'cancel_at_wait'):
            with self.subTest(mode=mode):
                transitions, waits = [], []
                model = object()
                array = engine['Array']
                env = dict(SetupRevision=10, _Positions=array([object()]), POSITION_COUNT_MAX=5,
                           LeadIn=True, _QuickResetScenes=False, _PrimaryScenes=array(['one']),
                           _LeadInScenes=array(), _CustomScenes=array(), _furniStatus=1,
                           STATE_SETUP='Making', STATE_SETUP_M='Making_M', self=model,
                           UnregisterForUpdate=lambda: None, GetState=lambda: 'Making',
                           Config=SimpleNamespace(HOOKID_STARTING=1, DebugMode=False), RunHook=lambda *a: None,
                           TraceStartupPhase=lambda *a: None,
                           GetSubmissives=lambda: array(), GoToState=transitions.append,
                           PapyrusUtil=SimpleNamespace(RemoveActor=lambda values, value: values))

                def create(*_):
                    if mode == 'normal':
                        env['_instanceCreationWaitLock'] = 1
                    elif mode == 'cancel_at_create':
                        env['SetupRevision'] += 1

                def wait(_):
                    waits.append(1)
                    self.assertLessEqual(len(waits), 1, 'cancelled setup remained in wait loop')
                    env['SetupRevision'] += 1

                env.update(CreateInstance=create, CreateInstanceForRevision=create,
                           Utility=SimpleNamespace(Wait=wait))
                result, _ = psc('sslThreadModel', 'StartThread', env)
                if mode == 'normal':
                    self.assertIs(result, model)
                    self.assertEqual(transitions, ['Making_M'])
                else:
                    self.assertIsNone(result)
                    self.assertEqual(transitions, [])

    def test_cancel_and_reuse_before_native_entry(self):
        array = engine['Array']
        calls = []
        env = dict(SetupRevision=10, _Positions=array([object()]), POSITION_COUNT_MAX=5,
                   LeadIn=True, _QuickResetScenes=False, _PrimaryScenes=array(['old-scene']),
                   _LeadInScenes=array(), _CustomScenes=array(), _furniStatus=1,
                   STATE_SETUP='Making', STATE_SETUP_M='Making_M', self=object(),
                   UnregisterForUpdate=lambda: None, Config=SimpleNamespace(HOOKID_STARTING=1, DebugMode=False),
                   TraceStartupPhase=lambda *a: None,
                   RunHook=lambda *a: None, GetSubmissives=lambda: array(),
                   PapyrusUtil=SimpleNamespace(RemoveActor=lambda values, value: values),
                   Utility=SimpleNamespace(Wait=lambda _: self.fail('old setup must not wait')),
                   GoToState=lambda _: self.fail('old setup must not advance'))

        state_calls = []

        def reuse_at_state_call():
            state_calls.append(1)
            # The new preflight check must pass before exercising the later
            # native-entry boundary that this regression originally covered.
            if len(state_calls) == 1 and 'string startState = GetState()' in engine['body']('sslThreadModel', 'StartThread'):
                return 'Making'
            # The first revision comparison already passed. Cancellation and a
            # new start occur during the remaining native GetState boundary.
            env['SetupRevision'] += 2
            env['_instanceCreationWaitLock'] = 37  # owned by the newer start
            return 'Making'

        def native_entry(*values):
            revision = values[5] if len(values) == 6 else env['SetupRevision']
            calls.append((revision, env['SetupRevision'], values[1]))

        env.update(GetState=reuse_at_state_call, CreateInstance=native_entry,
                   CreateInstanceForRevision=native_entry)
        result, _ = psc('sslThreadModel', 'StartThread', env)
        self.assertIsNone(result)
        self.assertEqual(calls, [(11, 13, ['old-scene'])])
        self.assertEqual(env['_instanceCreationWaitLock'], 37)

    def test_explicit_unregister_during_registration(self):
        self.surface_registration_overlap('void UnregisterInstanceNiSurface()', False)

    def test_published_destructor_during_first_registration(self):
        self.surface_registration_overlap('~Instance()', True)

    def surface_registration_overlap(self, operation, published):
        entered, release, attempted = threading.Event(), threading.Event(), threading.Event()
        mutex = threading.Lock()
        state, errors = {'present': False, 'owned': False}, []

        class Marker:
            def load(self):
                return state['owned']

            def exchange(self, value):
                old, state['owned'] = state['owned'], value
                return old

        def register():
            with mutex:
                entered.set()
                if not release.wait(2):
                    raise AssertionError('registration barrier was not released')
                state['present'] = True
            state['owned'] = True

        def unregister(_):
            attempted.set()
            with mutex:
                state['present'] = False

        marker = Marker()
        env = dict(ownsNiSurface=marker, niSurfaceWasRegistered=marker, wasPublished=published,
                   linkedQst=SimpleNamespace(GetFormID=lambda: 1),
                   Interaction=SimpleNamespace(NiSurface=SimpleNamespace(
                       Manager=SimpleNamespace(Unregister=unregister))))
        env['UnregisterInstanceNiSurface'] = lambda: surface_control('void UnregisterInstanceNiSurface()', env)

        def run(fn):
            try:
                fn()
            except Exception as error:
                errors.append(error)

        registering = threading.Thread(target=lambda: run(register))
        removing = threading.Thread(target=lambda: run(lambda: surface_control(operation, env)))
        registering.start()
        try:
            self.assertTrue(entered.wait(1))
            removing.start()
            reached_manager = attempted.wait(.5)
        finally:
            release.set()
            registering.join(2)
            if removing.ident is not None:
                removing.join(2)
        self.assertFalse(errors)
        self.assertTrue(reached_manager, operation + ' skipped the manager while registration was pending')
        self.assertFalse(state['present'])

    def test_unpublished_destructor_does_not_unregister_new_surface(self):
        for published in (False, True):
            calls, flag = [], [published]

            def exchange(value):
                old, flag[0] = flag[0], value
                return old

            marker = SimpleNamespace(load=lambda: flag[0], exchange=exchange)
            env = dict(niSurfaceWasRegistered=marker, ownsNiSurface=marker, wasPublished=published,
                       linkedQst=SimpleNamespace(GetFormID=lambda: 1),
                       Interaction=SimpleNamespace(NiSurface=SimpleNamespace(
                           Manager=SimpleNamespace(Unregister=lambda _: calls.append('unregister')))))
            env['UnregisterInstanceNiSurface'] = lambda: surface_control('void UnregisterInstanceNiSurface()', env)
            surface_control('~Instance()', env)
            self.assertEqual(len(calls), int(published))

    def test_native_cancel_and_reuse_contract(self):
        destroy = cpp_body('src/Thread/Thread.cpp', 'void Instance::DestroyInstance(')
        finalize = cpp_body('src/Thread/ThreadCtor.cpp', 'void Instance::FinalizeCenterRefSelection(')
        select = cpp_body('src/Thread/ThreadCtor.cpp', 'void Instance::SelectCenterReference(')
        self.assertIn('remove(pendingInstances)', destroy)
        self.assertIn('setupLock{ _mSetup }', destroy)
        self.assertIn('setupLock{ _mSetup }', finalize)
        self.assertIn('i->setupTicket == a_ticket', finalize)
        self.assertIn('instance->setupTicket != a_ticket', select)
        missing = finalize[finalize.index('if (it == pendingInstances.end())'):finalize.index('instance = std::move(*it)')]
        self.assertNotIn('DispatchContinueSetup', missing)
        self.assertGreater(destroy.index('retired.clear()'), destroy.index('remove(pendingInstances)'))

    def test_detached_request_captures_identity_before_start(self):
        wrapper = cpp_body('src/Papyrus/sslThreadModel.cpp', 'void CreateInstanceForRevision(QUESTARGS,')
        reserve = cpp_body('src/Thread/Thread.cpp', 'uint64_t Instance::ReserveSetupTicket(')
        create = cpp_body('src/Thread/Thread.cpp', 'void Instance::CreateInstance(')
        destroy = cpp_body('src/Thread/Thread.cpp', 'void Instance::DestroyInstance(')
        self.assertNotIn('GetProperty<int>', wrapper)
        self.assertLess(wrapper.index('ReserveSetupTicket(a_qst, a_revision)'), wrapper.index('std::thread('))
        self.assertIn('preference, ticket, a_revision)', wrapper)
        # An old reservation must not replace a newer request after cancellation/reuse.
        self.assertLess(reserve.index('"SetupRevision"'), reserve.index('setupRequests[a_linkedQst]'))
        self.assertIn('setupRequests.erase(a_linkedQst)', destroy)
        self.assertLess(create.index('IsCurrentSetup('), create.index('std::make_unique<Instance>'))

    def test_center_wait_and_menu_publication_contract(self):
        create = cpp_body('src/Thread/Thread.cpp', 'void Instance::CreateInstance(')
        center = cpp_body('src/Thread/ThreadCtor.cpp', 'Instance::InitializeCenter(')
        # The engine task and the worker continuation each validate ownership;
        # the blocking future itself must be outside both setup-lock scopes.
        self.assertGreaterEqual(center.count('IsCurrentSetup('), 2)
        self.assertRegex(center, r'\}\);\s*const bool selected = future.get\(\);\s*const std::lock_guard setupLock')
        self.assertLess(create.index('pendingInstances.emplace_back'), create.index('created->OpenCenterRefMenu()'))
        header = read('src/Thread/Thread.h')
        destructor = cpp_body('src/Thread/Thread.h', '~Instance()')
        self.assertIn('if (wasPublished)', destructor)
        self.assertGreater(create.index('created->wasPublished = true'), create.index('instances.emplace_back'))
        unreg = cpp_body('src/Thread/Thread.h', 'void UnregisterInstanceNiSurface()')
        self.assertNotIn('if (', unreg)

    def test_native_menu_handoff_contract(self):
        render = cpp_body('src/Thread/Interface/FurnSelectMenu.cpp', 'void FurnSelectMenu::Render()')
        select = cpp_body('src/Thread/Interface/FurnSelectMenu.cpp', 'void FurnSelectMenu::HandleSelection(')
        self.assertLess(render.index('lock.unlock()'), render.index('HandleSelection('))
        self.assertIn('_ticket != a_ticket', select)
        self.assertIn('Instance::SelectCenterReference(quest, a_ticket, a_index)', select)

    def test_scene_index_write_lock_contract(self):
        body = cpp_body('src/Registry/Library_SaveLoad.cpp', 'void Library::InitializeScenes()')
        at = body.index('sceneMap[scene->id]')
        self.assertRegex(body[:at].rstrip(), r'const std::unique_lock lock\{ _mScenes \};$')
        self.assertIn('scenePackages[scene.get()] = package.get()', body)

    def test_voice_clear_persistence_contract(self):
        clear = cpp_body('src/Registry/Library.cpp', 'void Library::ClearVoice(')
        save = cpp_body('src/Registry/Library_SaveLoad.cpp', 'void Library::SaveVoices()')
        get = cpp_body('src/Registry/Library.cpp', 'const Voice* Library::GetVoice(RE::Actor*')
        self.assertIn('removedVoiceCacheKeys.insert', clear)
        self.assertIn('cache.remove(key)', save)
        self.assertLess(save.index('cache.remove(key)'), save.index('cache[str] ='))
        self.assertIn('std::shared_lock lock{ _mVoice }', save)
        self.assertIn('std::unique_lock lock{ _mVoice }', get)
        self.assertNotIn('GetSavedVoice(', get)

    def test_statistics_access_lifetime_contract(self):
        header = read('src/Registry/Stats.h')
        get = cpp_body('src/Registry/Stats.cpp', 'StatisticsData::GetStatistics(')
        self.assertIn('std::unique_lock<std::shared_mutex> lock', header)
        self.assertIn('std::move(lock)', get)
        self.assertIn('std::optional<ActorEncounter> GetEncounter', header)
        for file in ('src/Papyrus/sslActorStats.cpp', 'src/Papyrus/sslThreadModel.cpp'):
            self.assertNotRegex(read(file), r'auto& stats = .*GetStatistics\(')

    def test_scene_conversion_and_lookup_cost_contract(self):
        text = read('src/Papyrus/sslThreadModel.cpp')
        a, b = text.index('GetPlayingScenes('), text.index('GetCustomScenes(')
        self.assertNotIn('return (acc.push_back', text[a:b])
        lookup = cpp_body('src/Registry/Library.cpp', 'const AnimPackage* Library::GetPackageFromScene(')
        self.assertIn('scenePackages.find(a_scene)', lookup)
        select = cpp_body('src/Thread/Interface/Elements/SceneSelectPanel.cpp', 'void SceneSelectPanel::OnSceneSelected(')
        self.assertNotIn('RebuildEntries', select)

    def test_numeric_placeholder_and_text_boundaries_contract(self):
        helper = cpp_body('src/Thread/Interface/StageSelectMenu.cpp', 'std::string ResolveNavTextPlaceholders(')
        self.assertNotIn('std::stoul', helper)
        self.assertIn('parsed.ec != std::errc{}', helper)
        strings = read('src/Util/StringUtil.h')
        self.assertNotIn('&*subrange.begin()', strings)
        self.assertIn('[](unsigned char c)', strings)
        self.assertIn('std::isspace(static_cast<unsigned char>(word.front()))', strings)
        random = read('src/Util/Random.h')
        self.assertIn('thread_local std::mt19937', random)
        self.assertIn('dist{ 0, v.size() - 1 }', random)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
