"""Review-only expected-contract probes. No engine or production writes.

Regression cases first failed against reviewed HEAD. Uses production helper
bodies through the existing limited Papyrus translator; source casts of Actor to
Actor are erased for the stand-in. Root runs this after complete repository review.
"""
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import importlib.util
import itertools
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import papyrus_harness as h


class CoreContractProbes(unittest.TestCase):
    def test_all_four_actor_permutations_preserve_alias_identity(self):
        original_expression = h.expression
        def cast_free(text):
            return original_expression(re.sub(r'\s+as\s+Actor\b', '', text, flags=re.I))
        with patch.object(h, 'expression', cast_free):
            for order in itertools.permutations('ABCD'):
                aliases = h.Array([NS(GetReference=lambda actor=actor: actor) for actor in 'ABCD'])
                fn = h.helper('sslThreadModel', 'SortAliasesToPositions', '', {
                    '_Positions': h.Array(), 'ActorAlias': aliases,
                    'GetPositions': lambda order=order: h.Array(order),
                }, state_names=('_Positions',))
                fn()
                self.assertEqual([alias.GetReference() for alias in aliases], list(order), order)

    def test_creature_masks_follow_declared_sex_bit_contract(self):
        env = {'Math': NS(LogicalAnd=lambda a, b: a & b), 'GetPositionSex': lambda _, value: value}
        creature = h.helper('SexlabRegistry', 'GetIsCreaturePositon', 'asID,n', env)
        female = h.helper('SexlabRegistry', 'GetIsFemaleCreaturePositon', 'asID,n', env)
        self.assertEqual([bool(creature('scene', x)) for x in (1,2,4,8,16)], [False,False,False,True,True])
        self.assertEqual([bool(female('scene', x)) for x in (1,2,4,8,16)], [False,False,False,False,True])

    def test_weapon_false_still_produces_33_strip_flags(self):
        fn = h.helper('sslUtility', 'BitsToBool', 'n, append', {
            'Math': NS(LogicalAnd=lambda a,b:a&b, LeftShift=lambda a,b:a<<b),
        })
        flags = fn(4, False)
        self.assertEqual(len(flags), 33)
        self.assertFalse(flags[32])

    def test_first_stage_uses_first_configured_timer(self):
        fn = h.helper('sslThreadModel', 'GetStageTimer', 'maxstage', {
            'Timers': h.Array([11,22,33,44]), '_StageHistory': h.Array(['']),
            'SexLabRegistry': NS(GetClimaxingActors=lambda *_: h.Array()),
            'GetActiveScene': lambda:'scene', 'GetActiveStage': lambda:'root',
        })
        self.assertEqual(fn(0), 11)

    def test_stat_registration_preserves_prefix_and_suffix(self):
        saved = {}
        fn = h.helper('sslActorStats', 'RegisterStat', "Stat, Value, Prepend='', Append=''", {
            'FindStat': lambda _: -1, 'Game': NS(GetPlayer=lambda:'player'),
            'SexLabStatistics': NS(SetCustomStatStr=lambda actor,key,value:saved.__setitem__((actor,key),value)),
        })
        fn('Score', '10', '[', ']')
        self.assertEqual(saved[('player','Custom.Prepend.Score')] + saved[('player','Score')] +
                         saved[('player','Custom.Append.Score')], '[10]')

    def test_failed_audio_conversion_preserves_source(self):
        path = ROOT / 'dist/Sound/fx/SexLab/vfx/ConvertMp3ToWav.py'
        spec = importlib.util.spec_from_file_location('review_convert', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.os, 'walk', return_value=[('fixture', [], ['sample.mp3'])]), \
             patch.object(module.os.path, 'exists', return_value=False), \
             patch.object(module.subprocess, 'run', return_value=NS(returncode=1)), \
             patch.object(module.os, 'remove') as remove:
            module.convert_mp3_to_wav('fixture')
            remove.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
