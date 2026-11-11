"""Native review repair contracts and independent mathematical references.

No C++ compiler, game engine, VM or actual concurrent native execution is used.
--baseline-ref HEAD demonstrates the original reviewed-source failures.
"""
from pathlib import Path
import argparse
import itertools
import math
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


def body(path, signature):
    text = source(path)
    start = text.index(signature)
    a = start + re.search(r'\n[ \t]*\{', text[start:]).end() - 1
    b, depth = a + 1, 1
    while depth:
        depth += (text[b] == '{') - (text[b] == '}')
        b += 1
    return text[a:b]


class NativeReviewRepairs(unittest.TestCase):
    def test_partner_quota_scan_revisits_skipped_candidates(self):
        text = body('src/Papyrus/sslLibrary/sslThreadLibrary.cpp', 'std::vector<RE::Actor*> FindAvailablePartners(')
        self.assertIn('while (added)', text)
        self.assertIn('std::ranges::contains(a_positions, actor)', text)

        def select(available, male_count, female_count, total, initial=()):
            result = list(initial)
            genders = {'M': result.count('M'), 'F': result.count('F')}
            while len(result) < total:
                added = False
                for identity, sex in available:
                    if any(existing[0] == identity for existing in result if isinstance(existing, tuple)):
                        continue
                    target = 'M' if genders['M'] < male_count else 'F' if genders['F'] < female_count else None
                    if target is None or sex == target:
                        result.append((identity, sex))
                        genders[sex] += 1
                        added = True
                        if len(result) == total:
                            return result
                if not added:
                    break
            return result

        for sexes in [('F', 'M'), ('F', 'F', 'M', 'M'), ('M', 'F', 'M', 'F')]:
            for permutation in itertools.permutations(enumerate(sexes)):
                result = select(permutation, sexes.count('M'), sexes.count('F'), len(sexes))
                self.assertEqual(len(result), len(sexes))
                self.assertEqual(len({actor[0] for actor in result}), len(result))
        self.assertEqual(select([(0, 'F')], 1, 1, 2), [])

    def test_bedroll_fallback_rotation_uses_radians(self):
        header = source('src/Registry/Library.h')
        line = next(line for line in header.splitlines() if 'offsetDefaultBedroll{' in line)
        self.assertIn('glm::radians(180.0f)', line)
        self.assertAlmostEqual(math.degrees(math.radians(180.0)) % 360, 180.0)

    def test_world_bounds_consider_every_corner(self):
        text = body('src/Registry/Util/RayCast/ObjectBound.cpp', 'std::optional<ObjectBound> ObjectBound::MakeBoundingBox(')
        self.assertIn('corner < 8', text)
        self.assertIn('glm::min(bound.worldBoundMin, world)', text)
        self.assertIn('glm::max(bound.worldBoundMax, world)', text)
        lo, hi = (-1., -2., -3.), (1., 2., 3.)
        for degrees in (0., 45., 90., 180., 233.24):
            radians = math.radians(degrees)
            c, s = math.cos(radians), math.sin(radians)
            points = [(x*c-y*s+100, x*s+y*c-40, z+7)
                      for x, y, z in itertools.product(*zip(lo, hi))]
            minimum = [min(p[axis] for p in points) for axis in range(3)]
            maximum = [max(p[axis] for p in points) for axis in range(3)]
            center = (100., -40., 7.)
            self.assertTrue(all(minimum[i] <= center[i] <= maximum[i] for i in range(3)))
            self.assertTrue(all(minimum[i] <= p[i] <= maximum[i] for i in range(3) for p in points))

    def test_invalid_scaling_has_loader_and_runtime_fallback(self):
        constructor = body('src/Registry/Define/Expression.cpp', 'Expression::Expression(const YAML::Node&')
        self.assertIn('scaling < Scaling::Linear || scaling >= Scaling::Total', constructor)
        data = body('src/Registry/Define/Expression.cpp', 'Expression::GetData(')
        self.assertIn('float multiplier = a_strength / 100.0f;', data)
        self.assertRegex(data, r'default:\s*break;')

    def test_scene_reads_copy_while_shared_lock_is_owned(self):
        read = body('src/Registry/Library.cpp', 'bool Library::ReadScene(')
        self.assertIn('std::shared_lock lock{ _mScenes }', read)
        self.assertLess(read.index('std::shared_lock'), read.index('a_func('))
        for signature in ('bool HasSceneAnnotation(', 'std::vector<RE::BSFixedString> GetSceneAnnotations(',
                          'bool HasPositionAnnotation(', 'std::vector<RE::BSFixedString> GetPositionAnnotations(',
                          'bool IsSceneTag(', 'bool IsSceneTagA('):
            with self.subTest(signature=signature):
                read = body('src/Papyrus/SexLabRegistry.cpp', signature)
                self.assertIn('ReadScene(a_id,', read)
        common = body('src/Papyrus/SexLabRegistry.cpp', 'std::vector<RE::BSFixedString> GetCommonTags(')
        self.assertIn('ReadScene(sceneid,', common)


if __name__ == '__main__':
    unittest.main(argv=['full_review_native_0f.py'], verbosity=2)
