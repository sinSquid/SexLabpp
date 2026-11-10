"""Read native repair contracts without invoking a compiler.

Source assertions plus bounded arithmetic/matching witnesses; these are not
C++ execution, YAML runtime, Papyrus VM or native concurrency tests.
--baseline-ref demonstrates that the reviewed snapshot fails the contracts.
"""
from pathlib import Path
import argparse
import itertools
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()


def read(path):
    if args.baseline_ref:
        return subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{path}'], cwd=ROOT).decode('utf-8-sig')
    return (ROOT / path).read_text(encoding='utf-8-sig')


def body(path, signature):
    text = read(path)
    start = text.index(signature)
    begin = text.index('{', start)
    end, depth = begin + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]


class NativeReviewRepairs(unittest.TestCase):
    def test_reset_statistics_is_bound(self):
        self.assertRegex(read('src/Papyrus/sslActorStats.h'),
                         r'REGISTERFUNC\(ResetStatistics, "SexLabStatistics", true\)')

    def test_scene_overrides_round_trip_contract(self):
        save = body('src/Registry/Define/Animation.cpp', 'void Scene::Save(')
        load = body('src/Registry/Define/Animation.cpp', 'void Scene::Load(')
        for key in ('scene_offset', 'scene_annotations', 'position_annotations'):
            self.assertIn('"' + key + '"', save)
            self.assertIn('"' + key + '"', load)
        self.assertIn('YAML::NodeType::Sequence', save)  # Empty overrides must persist removal.
        self.assertIn('tags.SetAnnotations(', load)
        self.assertIn('positions[i].annotations', load)
        self.assertIn('furnitureOffset.Load(', load)

    def test_nearest_furniture_uses_world_space(self):
        fn = body('src/Registry/Define/Furniture.cpp', 'FurnitureDetails::GetClosestCoordinatesInBound(')
        self.assertIn('a.ApplyReturn(reference).GetDistance(center)', fn)
        self.assertIn('b.ApplyReturn(reference).GetDistance(center)', fn)
        bounds = body('src/Registry/Define/Furniture.cpp', 'FurnitureDetails::GetCoordinatesInBound(')
        self.assertIn('offset.ApplyReturn(referenceCoordinates)', bounds)
        # Translation + rotation must preserve the returned LOCAL offset.
        for rotation in (0, 90, 180):
            import math
            angle = math.radians(-rotation)
            candidates = [(0, 0), (10, 0)]
            ref = (100, 50)
            world = [(ref[0] + x * math.cos(angle) - y * math.sin(angle),
                      ref[1] + x * math.sin(angle) + y * math.cos(angle)) for x, y in candidates]
            target = (world[0][0] + .1, world[0][1])
            choice = min(range(2), key=lambda i: math.dist(world[i], target))
            self.assertEqual(candidates[choice], (0, 0))

    def test_reverse_role_mapping(self):
        fn = body('src/Registry/Stats.cpp', 'void StatisticsData::AddEncounter(')
        conversions = dict(re.findall(r'case ActorEncounter::EncounterType::(\w+):\s*a_type = ActorEncounter::EncounterType::(\w+);', fn))
        self.assertEqual(conversions, dict(Aggressor='Victim', Victim='Aggressor',
                                          Submissive='Dominant', Dominant='Submissive'))
        for key, value in conversions.items():
            self.assertEqual(conversions[value], key)

    def test_partner_matching_reassigns_used_candidates(self):
        fn = body('src/Papyrus/sslLibrary/sslThreadLibrary.cpp', 'FindAnimationPartnersImpl(')
        self.assertIn('assignPosition', fn)
        self.assertIn('candidateOwner', fn)
        self.assertIn('visited', fn)
        self.assertIn('assignPosition(assignPosition,', fn)
        # Independently check the augmenting-path strategy against exhaustive
        # matching for all 3x3 compatibility graphs, plus the reviewed counterexample.
        def match(slots, candidate_count):
            owner = [-1] * candidate_count
            result = [-1] * len(slots)
            def assign(slot, seen):
                for pass_index in range(2):
                    for candidate in range(candidate_count):
                        if candidate in seen or candidate not in slots[slot]:
                            continue
                        if (pass_index == 0) != (owner[candidate] < 0):
                            continue
                        seen.add(candidate)
                        if owner[candidate] == -1 or assign(owner[candidate], seen):
                            owner[candidate] = slot
                            result[slot] = candidate
                            return True
                return False
            return result if all(assign(slot, set()) for slot in range(len(slots))) else []
        self.assertEqual(match([{0, 1}, {0}], 2), [1, 0])
        self.assertEqual(match([{0, 1}, {0, 1}], 2), [0, 1])
        for bits in range(512):
            slots = [{j for j in range(3) if bits & (1 << (i * 3 + j))} for i in range(3)]
            possible = any(all(candidate in slots[i] for i, candidate in enumerate(order))
                           for order in itertools.permutations(range(3)))
            self.assertEqual(bool(match(slots, 3)), possible, bits)

    def test_bed_markers_not_localized_name(self):
        fn = body('src/Registry/Define/Furniture.cpp', 'FurnitureType FurnitureType::GetBedType(')
        self.assertNotIn('GetName()', fn)
        self.assertIn('AnimationType::kSleep', fn)
        self.assertIn('FurnitureBedRoll', fn)

    def test_expression_level_bounds_at_both_entry_points(self):
        for path, sig in [('src/Papyrus/sslObject/sslExpressionSlots.cpp', 'void SetValues('),
                          ('src/Registry/Define/Expression.cpp', 'void Expression::UpdateValues(')]:
            fn = body(path, sig)
            self.assertIn('a_level < 0', fn)
            self.assertIn('MAX_LEVEL_COUNT', fn)
            if 'dataEntry' in fn:
                self.assertLess(fn.index('a_level < 0'), fn.index('dataEntry'))

    def test_slr_counts_checked_before_allocation(self):
        scene = body('src/Registry/Define/Animation.cpp', 'Scene::Scene(')
        stage = body('src/Registry/Define/Animation.cpp', 'Stage::Stage(')
        self.assertIn('info_count == 0', scene)
        self.assertIn('ActorFragment::MAX_ACTOR_COUNT', scene)
        self.assertLess(scene.index('info_count == 0'), scene.index('positions.reserve(info_count)'))
        self.assertIn('position_count != a_expectedPositions', stage)
        self.assertLess(stage.index('position_count != a_expectedPositions'), stage.index('positions.reserve(position_count)'))

    def test_profile_snapshots_retain_lock_until_copy(self):
        for typ, mutex in [('Voice', '_mVoice'), ('Expression', '_mExpressions')]:
            fn = body('src/Registry/Library.cpp', f'Library::Get{typ}Snapshot(')
            self.assertIn(f'std::shared_lock lock{{ {mutex} }}', fn)
            self.assertIn(f'std::optional<{typ}>', fn)
        expressions = read('src/Papyrus/sslObject/sslExpressionSlots.cpp')
        voices = read('src/Papyrus/sslObject/sslVoiceSlots.cpp')
        self.assertIn('GetExpressionSnapshot(a_id)', expressions)
        self.assertIn('GetVoiceSnapshot(a_id)', voices)
        self.assertNotIn('p->has_edits = true', expressions)


if __name__ == '__main__':
    unittest.main(argv=['native review repairs'], verbosity=2)
