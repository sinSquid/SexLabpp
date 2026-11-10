"""No-compiler thread/UI regressions for the 2026-11-11 full review fixes.

Checks production ownership/synchronization contracts and bounded Python
stand-ins. These are not native execution, a Papyrus VM, or game-render tests.
--baseline-ref HEAD runs the same source checks on the pre-fix commit.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import math
import re
import subprocess
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
ARGS = parser.parse_args()


def source(path):
    if ARGS.baseline_ref:
        return subprocess.check_output(['git', 'show', f'{ARGS.baseline_ref}:{path}'], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8-sig')


def function(path, signature):
    text = source(path)
    start = text.index(signature)
    brace, depth = text.index('{', start), 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


class ThreadReviewRegressions(unittest.TestCase):
    def test_choice_is_bound_to_session_scene_and_stage(self):
        body = function('src/Thread/Interface/StageSelectMenu.cpp', 'bool StageSelectMenu::IsChoiceCurrent()')
        expression = re.search(r'return (.*?);', body, re.S)[1]
        expression = expression.replace('instance->', 'instance.').replace('&&', ' and ')
        expression = expression.replace('GetThreadProperty<int>("PlaybackRevision")', 'GetPlaybackRevision()')
        instance = NS(GetSetupTicket=lambda: 10, GetActiveScene=lambda: 'scene',
                      GetActiveStage=lambda: 'stage', GetPlaybackRevision=lambda: 7)
        good = dict(instance=instance, _choicePending=True, _choiceSetupTicket=10,
                    _choiceScene='scene', _choiceOrigin='stage', _choiceRevision=7)
        expression = ' '.join(expression.split())
        self.assertTrue(eval(expression, good))
        for key, value in (('_choicePending', False), ('instance', None), ('_choiceSetupTicket', 9),
                           ('_choiceScene', 'new-scene'), ('_choiceOrigin', 'new-stage'), ('_choiceRevision', 6)):
            with self.subTest(key=key):
                self.assertFalse(eval(expression, dict(good, **{key: value})))

    def test_choice_teardown_preserves_other_thread_window(self):
        close = function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::CloseForThread(')
        self.assertIn('a_quest && a_quest == _linkedThread', close)
        destroy = function('src/Thread/Thread.cpp', 'void Instance::DestroyInstance(')
        self.assertIn('StageSelectMenu::GetSingleton().CloseForThread(a_linkedQst)', destroy)
        render = function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::Render()')
        self.assertLess(render.index('!IsChoiceCurrent()'), render.index('RenderStageChoiceCard()'))

    def test_queued_choice_uses_guarded_papyrus_endpoint(self):
        dispatch = function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::OnNextBranchSelected(')
        self.assertLess(dispatch.index('!IsChoiceCurrent()'), dispatch.index('DispatchMethodCall'))
        self.assertIn('"BranchToForRevision"', dispatch)
        self.assertIn('int{ _choiceRevision }', dispatch)
        self.assertIn('RE::BSFixedString{ _choiceScene->id }', dispatch)
        self.assertIn('RE::BSFixedString{ _choiceOrigin->id }', dispatch)
        controller = source('dist/Source/Scripts/sslThreadController.psc')
        body = re.search(r'(?ims)^Function BranchToForRevision\([^\n]*\)\s*\n(.*?)^EndFunction', controller)[1]
        self.assertIn('IsCurrentPlayback(aiRevision)', body)
        self.assertIn('GetActiveScene() != asSceneId', body)
        self.assertIn('GetActiveStage() != asStageId', body)

    def test_graph_click_and_close_also_validate_queued_origin(self):
        graph = function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::RenderSceneGraphView()')
        self.assertIn('"SkipToFromGraphForRevision"', graph)
        self.assertIn('"CloseGraphForRevision"', graph)
        self.assertNotIn('"SkipTo"', graph)
        self.assertLess(graph.index('!inst->GetActiveStage()'), graph.index('ImGuiMCP::Begin('))
        controller = source('dist/Source/Scripts/sslThreadController.psc')
        body = re.search(r'(?ims)^Function SkipToFromGraphForRevision\([^\n]*\)\s*\n(.*?)^EndFunction', controller)[1]
        self.assertIn('IsCurrentPlayback(aiRevision)', body)
        self.assertIn('GetActiveScene() != asSceneId', body)
        self.assertIn('GetActiveStage() != asStageId', body)
        self.assertLess(body.index('CloseGraphForRevision'), body.index('SkipTo(asTarget)'))

    def test_scoped_lookup_prevents_destroy_until_operation_finishes(self):
        header = source('src/Thread/Thread.h')
        access = header[header.index('class Access'):header.index('Instance(RE::TESQuest*')]
        self.assertIn('std::unique_lock<std::recursive_mutex> lock', access)
        self.assertIn('explicit operator bool()', access)
        self.assertNotIn('operator Instance*', access)
        lookup = function('src/Thread/Thread.cpp', 'Instance::Access Instance::GetInstance(')
        self.assertLess(lookup.index('LockState()'), lookup.index('_mInstances'))
        self.assertIn('std::move(stateLock), instance.get()', lookup)
        destroy = function('src/Thread/Thread.cpp', 'void Instance::DestroyInstance(')
        self.assertLess(destroy.index('_mSetup'), destroy.index('retired.clear()'))
        # The source contract establishes both paths use the same mutex. Model
        # the lifetime guarantee with a barrier, not scheduling sleeps.
        lock, entered, finished = threading.RLock(), threading.Event(), threading.Event()
        node = {'alive': True}

        def retire():
            entered.set()
            with lock:
                node['alive'] = False
            finished.set()

        with lock:
            worker = threading.Thread(target=retire)
            worker.start()
            self.assertTrue(entered.wait(1))
            self.assertFalse(finished.is_set())
            self.assertTrue(node['alive'])
        worker.join(2)
        self.assertTrue(finished.is_set())
        self.assertFalse(node['alive'])

    def test_manager_and_frame_lock_order_is_state_first(self):
        file = 'src/Thread/Interaction/NiSurface/CollisionManager.cpp'
        for name in ('void Manager::OnFrameUpdate(', 'std::shared_ptr<Scene> Manager::Get(',
                     'std::shared_ptr<Scene> Manager::Register(', 'void Manager::Unregister(',
                     'bool Scene::VisitPositions(', 'std::optional<ShaftSize> Scene::GetShaftSize('):
            with self.subTest(name=name):
                body = function(file, name)
                self.assertLess(body.index('Instance::LockState()'), body.index('_mutex'))
        for name in ('void Instance::CancelPendingAnimations(', 'void Instance::UpdateAnimations('):
            body = function('src/Thread/ThreadAnimation.cpp', name)
            self.assertLess(body.index('LockState()'), body.index('_mInstances'))
        # Initialization's engine-task wait must remain outside the state lock.
        center = function('src/Thread/ThreadCtor.cpp', 'Instance::InitializeCenter(')
        self.assertRegex(center, r'\}\);\s*const bool selected = future.get\(\);\s*const std::lock_guard setupLock')

    def test_hud_render_and_mutation_share_state_guard(self):
        path = 'src/Thread/Interface/SceneHUD.cpp'
        for name in ('void SceneHUD::Render()', 'void SceneHUD::Init(', 'void SceneHUD::Destroy()',
                     'void SceneHUD::SetFocus(', 'void SceneHUD::UpdateEnjoyment(',
                     'void SceneHUD::UpdateHighlightedPartner(', 'void SceneHUD::RebuildSceneList()',
                     'void SceneHUD::DebugNodeDrawBeginFrame()'):
            with self.subTest(name=name):
                body = function(path, name)
                self.assertRegex(body, r'\{\s*const auto stateLock = Instance::LockState\(\);')
        for name in ('void FurnSelectMenu::Render()', 'void FurnSelectMenu::Open(', 'void FurnSelectMenu::Close('):
            body = function('src/Thread/Interface/FurnSelectMenu.cpp', name)
            self.assertLess(body.index('Instance::LockState()'), body.index('_mutex'))

    def test_bar_layout_interval_is_valid_at_supported_scales(self):
        layout = function('src/Thread/Interface/Elements/EnjBarsOverlay.cpp', 'EnjBarsOverlay::Layout EnjBarsOverlay::GetLayout(')
        self.assertIn('std::min(dw * 0.15f, maxZoneWidth)', layout)
        scale = source('src/Thread/Interface/UI/Scale.h')
        self.assertIn('kUiScaleLow = 4.0f / 3.0f', scale)
        self.assertIn('kUiScaleHigh = 3.0f', scale)
        for width, height in ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160), (5120, 1440)):
            shortest = min(width, height)
            resolution = ((4 / 3) * shortest / 900 if shortest <= 900 else
                          3 * shortest / 2160 if shortest >= 2160 else
                          4 / 3 + (shortest - 900) / 1260 * (3 - 4 / 3))
            for multiplier in (.5, .75, 1., 1.5, 2.5):
                with self.subTest(display=(width, height), multiplier=multiplier):
                    factor = resolution * multiplier
                    upper = 360 * factor
                    lower = min(width * .15, upper)
                    actual = max(lower, min(260 * factor, upper))
                    self.assertLessEqual(lower, upper)
                    self.assertTrue(lower <= actual <= upper)
                    self.assertTrue(math.isfinite(actual))


if __name__ == '__main__':
    unittest.main(argv=['full_review_thread_1111.py'], verbosity=2)
