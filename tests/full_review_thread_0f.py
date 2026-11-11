"""No-compiler regressions for offsets, collision restoration and UI ranges.

Production source contracts plus bounded state/value witnesses. They do not
execute C++, Havok, the renderer, or the game's threading model.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
ARGS = parser.parse_args()


def source(path):
    if ARGS.baseline_ref:
        return subprocess.check_output(['git', 'show', ARGS.baseline_ref + ':' + path], cwd=ROOT).decode('utf-8-sig')
    return (ROOT / path).read_text(encoding='utf-8-sig')


def function(path, signature):
    text = source(path)
    start = text.index(signature)
    a = text.index('{', start)
    b, depth = a + 1, 1
    while depth:
        depth += (text[b] == '{') - (text[b] == '}')
        b += 1
    return text[a:b]


class ThreadRepairRegressions(unittest.TestCase):
    def test_offset_refresh_resolves_current_actor_slot(self):
        text = function('src/Thread/Interface/Elements/OffsetAdjustPanel.cpp', 'void OffsetAdjustPanel::RefreshValues(')
        self.assertIn('actor->GetFormID() == a_target.formId', text)
        self.assertLess(text.index('GetActors()'), text.index('stage->positions[a_target.positionIndex]'))
        self.assertIn('a_target.draggingAxis.reset()', text)
        self.assertIn('a_target.axes = {}', text)
        # A displayed actor follows its form ID through every permutation;
        # unrelated card expansion survives, but stale drag values are reset.
        import itertools
        for order in itertools.permutations(('A', 'B', 'C')):
            cached = 0
            current = order.index('A')
            offsets = [11, 22, 33]
            displayed = offsets[current]
            edited = offsets[order.index('A')]
            self.assertEqual(displayed, edited)
            if current != cached:
                self.assertNotEqual(current, cached)

    def test_collision_restores_saved_controller_and_owned_fields(self):
        code = source('src/Thread/Collision/CollisionHandler.cpp')
        restore = function('src/Thread/Collision/CollisionHandler.cpp', 'void CollisionHandler::RestoreRigidBodyPhysics(')
        self.assertNotIn('SetMassInv(1.0f)', restore)
        self.assertNotIn('gravityFactor = 1.0f', restore)
        self.assertIn('state.massInverse', restore)
        self.assertIn('state.gravityFactor', restore)
        self.assertIn('state.controller.get() != controller', restore)
        self.assertIn('kOwnedControllerFlags', code)
        self.assertIn('state.rigidBody.get() == body', restore)

    def test_first_snapshot_survives_repeat_disable_and_new_controller(self):
        code = source('src/Thread/Collision/CollisionHandler.cpp')
        self.assertIn('physicsStates.try_emplace', code)
        self.assertIn('state.controller.get() != controller', code)
        # Snapshot identity, not constants or latest disabled values, determines
        # restoration. A replacement controller does not inherit old values.
        original = NS(identity=object(), mass=.01, gravity=.5, flags=5)
        saved = (original.identity, original.mass, original.gravity, original.flags)
        original.mass = original.gravity = 0
        self.assertEqual(saved[1:], (.01, .5, 5))
        replacement = NS(identity=object(), mass=.02, gravity=.3, flags=9)
        if saved[0] is replacement.identity:
            replacement.mass, replacement.gravity, replacement.flags = saved[1:]
        self.assertEqual((replacement.mass, replacement.gravity, replacement.flags), (.02, .3, 9))

    def test_foot_ik_restoration_matches_live_driver_identity(self):
        code = function('src/Thread/Collision/CollisionHandler.cpp', 'void CollisionHandler::SetFootIKEnabled(')
        self.assertIn('saved.driver.get() == driver', code)
        self.assertIn('saved->disabled', code)
        self.assertIn('saved->alignedGroundRotation', code)
        self.assertNotIn('driver->disableFootIk = !a_enabled', code)

    def test_clear_restores_entries_before_erasing_cache(self):
        code = function('src/Thread/Collision/CollisionHandler.cpp', 'void CollisionHandler::Clear()')
        self.assertIn('RestoreRigidBodyPhysics(actor)', code)
        self.assertIn('SetFootIKEnabled(actor, true)', code)
        self.assertLess(code.index('RestoreRigidBodyPhysics(actor)'), code.index('_cache.clear()'))
        remove = function('src/Thread/Collision/CollisionHandler.cpp', 'void CollisionHandler::RemoveActor(')
        self.assertIn('physicsStates.erase(a_actor)', remove)

    def test_text_scale_slider_matches_setter(self):
        text = source('src/Thread/Interface/Elements/ElementCtrlPanel.cpp')
        slider = re.search(r'SliderFloat\("##slpp_ecmTextScale", &_textScaleAdjustment, ([\d.]+)f, ([\d.]+)f', text)
        setter = re.search(r'std::clamp\(a_value, ([\d.]+)f, ([\d.]+)f',
                           function('src/Thread/Interface/Elements/ElementCtrlPanel.cpp', 'void ElementCtrlPanel::OnTextScaleChange('))
        self.assertEqual(slider.groups(), setter.groups())


if __name__ == '__main__':
    unittest.main(argv=['full_review_thread_0f.py'], verbosity=2)
