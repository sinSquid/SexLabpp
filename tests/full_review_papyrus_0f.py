"""Production PSC regression bodies; no compiler, Papyrus VM or game required.

The bounded interpreter is reused from the existing suite. Native APIs and
engine objects are stand-ins; source/index checks do not execute the MCM UI.
--baseline-ref HEAD demonstrates the reviewed pre-fix behavior.
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
        return subprocess.check_output(['git', 'show', args.baseline_ref + ':' + path], cwd=ROOT).decode('utf-8-sig')
    return (ROOT / path).read_text(encoding='utf-8-sig')


engine = {'__file__': str(ROOT / 'tests/papyrus_confirmed_regressions.py')}
text = (ROOT / 'tests/papyrus_confirmed_regressions.py').read_text(encoding='utf-8')
argv = sys.argv
try:
    sys.argv = [argv[0]]
    # Preserve the real execution scope to observe property/reset side effects.
    prefix = text[:text.index('\nutility = NS(')].replace('scope = dict(env)', 'scope = env')
    exec(prefix, engine)
finally:
    sys.argv = argv
engine['source'] = source
Array = engine['Array']


def call(name, function, env, occurrence=0):
    return engine['execute'](engine['body'](name, function, occurrence), env)


def getter(name, property_name):
    prop = re.search(r'(?is)\bProperty\s+' + property_name + r'\s+hidden(.*?)EndProperty', source(name))[1]
    return re.search(r'(?is)Function Get\(\)(.*?)EndFunction', prop)[1]


class PapyrusFullReviewFixes(unittest.TestCase):
    def test_expression_editor_group_indices_match_storage(self):
        text = engine['body']('sslConfigMenu', 'ExpressionEditor')
        modifier = re.search(r'AddSliderOptionST\("expredit_" \+ (.*?) \+ "_" \+ i, "\$SSL_Modifier_" \+ n, values\[(.*?)\]', text)
        phoneme = re.search(r'AddSliderOptionST\("expredit_" \+ (.*?) \+ "_" \+ i, "\$SSL_Phoneme_" \+ k, values\[(.*?)\]', text)
        self.assertIsNotNone(modifier)
        self.assertIsNotNone(phoneme)
        for n in range(14):
            env = dict(n=n, k=0)
            self.assertEqual(eval(modifier[1], env), 16 + n)
            self.assertEqual(eval(modifier[2], env), 16 + n)
        for k in range(16):
            env = dict(n=14, k=k)
            self.assertEqual(eval(phoneme[1], env), k)
            self.assertEqual(eval(phoneme[2], env), k)

    def test_full_initialize_clears_custom_timers(self):
        no = lambda *a, **kw: None
        env = dict(SetupRevision=7, UnregisterForUpdate=no, UnregisterForUpdateGameTime=no,
                   Config=NS(DisableThreadControl=no, StageTimer=Array([10., 15.])), self=object(),
                   ActorAlias=Array(), CenterAlias=NS(TryToClear=no),
                   PapyrusUtil=NS(ActorArray=lambda n: Array()),
                   Utility=NS(CreateStringArray=lambda n: Array(), CreateFloatArray=lambda n: Array([0.] * n)),
                   FURNI_ALLOW=1, DestroyInstance=no, GoToState=no, STATE_IDLE='Unlocked',
                   _CustomTimers=Array([77., 88.]))
        call('sslThreadModel', 'Initialize', env, 1)
        result, _ = engine['execute'](getter('sslThreadModel', 'Timers'), env)
        self.assertEqual(result, [10., 15.])
        # A custom setter remains valid until full Initialize; no quick-reset path clears it.
        for method in ('ResetScene', 'ResetAnimationQuick'):
            self.assertNotIn('_CustomTimers =', engine['body']('sslThreadModel', method))

    def test_find_empty_uses_actual_free_alias_without_skip(self):
        for slots, expected in (([], -1), ([True], -1), ([False], 0),
                                ([True, False, False], 1), ([True, None, False], 2)):
            with self.subTest(slots=slots):
                aliases = Array([None if occupied is None else NS(Registered=occupied) for occupied in slots])
                env = dict(GetAliases=lambda: aliases, SyncBackend=lambda: None,
                           Slotted=sum(occupied is True for occupied in slots),
                           GetNthAlias=lambda i: aliases[i] if 0 <= i < len(aliases) else None)
                result, _ = call('sslExpressionSlots', 'FindEmpty', env)
                self.assertEqual(result, expected)

    def test_successful_registration_initializes_exact_returned_alias(self):
        for succeeds in (False, True):
            with self.subTest(succeeds=succeeds):
                alias = NS(Registry='', GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION='marker')
                env = dict(Registrar='NewProfile', Registry=Array(), RegisterLock=False,
                           FindEmpty=lambda: 0, FindByRegistrar=lambda _: -1,
                           GetBySlot=lambda _: alias, GetNthAlias=lambda _: alias,
                           sslBaseExpression=NS(CreateEmptyProfile=lambda _: succeeds),
                           Utility=NS(WaitMenuMode=lambda _: None))
                result, _ = call('sslExpressionSlots', 'Register', env)
                self.assertEqual(result, 0 if succeeds else -1)
                self.assertEqual(alias.Registry, 'NewProfile' if succeeds else '')
                self.assertFalse(env['RegisterLock'])

    def test_registration_duplicate_and_full_do_not_create(self):
        for duplicate, available in ((True, 0), (False, -1)):
            calls = []
            env = dict(Registrar='Profile', Registry=Array(['Profile'] if duplicate else []),
                       RegisterLock=False, FindEmpty=lambda: available,
                       FindByRegistrar=lambda _: 0 if duplicate else -1,
                       sslBaseExpression=NS(CreateEmptyProfile=lambda _: calls.append('create') or True),
                       Utility=NS(WaitMenuMode=lambda _: None))
            result, _ = call('sslExpressionSlots', 'Register', env)
            self.assertEqual(result, -1)
            self.assertEqual(calls, [])
            self.assertFalse(env['RegisterLock'])

    def test_waiting_registration_rechecks_duplicate_after_lock(self):
        calls = []
        env = dict(Registrar='Profile', Registry=Array(), RegisterLock=True,
                   FindEmpty=lambda: calls.append('find') or 0,
                   sslBaseExpression=NS(CreateEmptyProfile=lambda _: calls.append('create') or True))

        def completed_while_waiting(_):
            env['Registry'] = Array(['Profile'])
            env['RegisterLock'] = False

        env['Utility'] = NS(WaitMenuMode=completed_while_waiting)
        result, _ = call('sslExpressionSlots', 'Register', env)
        self.assertEqual(result, -1)
        self.assertEqual(calls, [])
        self.assertFalse(env['RegisterLock'])

    def test_public_registration_returns_the_bound_alias_and_callback_slot(self):
        aliases = Array([NS(Registry='Old', Registered=True),
                         NS(Registry='', Registered=False,
                            GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION='marker')])
        effects = []
        common = dict(Registry=Array(['Old']), RegisterLock=False, GetAliases=lambda: aliases,
                      GetBySlot=lambda n: aliases[n], GetNthAlias=lambda n: aliases[n],
                      SyncBackend=lambda: None, Utility=NS(WaitMenuMode=lambda _: None),
                      sslBaseExpression=NS(CreateEmptyProfile=lambda name: effects.append(('create', name)) or True))

        def find_empty():
            return call('sslExpressionSlots', 'FindEmpty', dict(common))[0]

        def register(name):
            return call('sslExpressionSlots', 'Register', dict(common, Registrar=name, FindEmpty=find_empty))[0]

        for name, expected_slot in (('Old', 0), ('New', 1)):
            with self.subTest(name=name):
                env = dict(common, Registrar=name, Register=register,
                           CallbackForm=object(), CallbackAlias=None,
                           sslObjectFactory=NS(SendCallback=lambda registrar, slot, *unused:
                                               effects.append(('callback', registrar, slot))))
                result, _ = call('sslExpressionSlots', 'RegisterExpression', env)
                self.assertIs(result, aliases[expected_slot])
                self.assertEqual(result.Registry, name)
                self.assertEqual(effects[-1], ('callback', name, expected_slot))
        self.assertEqual([entry for entry in effects if entry[0] == 'create'], [('create', 'New')])

    def test_runtime_sums_selected_max_path_stage_lengths(self):
        for path, lengths, timers, expected in (
            (['first', 'last'], {'first': 5., 'last': 20.}, [10., 15.], 25.),
            (['first', 'middle', 'last'], {'first': 5., 'middle': 0., 'last': 0.}, [10., 15.], 35.),
            ([], {}, [10., 15.], 0.),
            (['only'], {'only': 0.}, [9.], -1.)):
            with self.subTest(path=path):
                seen = []
                env = dict(StageTimers=Array(timers), Registry='scene', GetMaxDepth=lambda: len(path),
                           SexLabRegistry=NS(GetPathMax=lambda *a: Array(path),
                                             GetStartAnimation=lambda _: path[0] if path else '',
                                             GetFixedLength=lambda _, stage: seen.append(stage) or lengths[stage]))
                value, _ = call('sslBaseAnimation', 'GetTimersRunTime', env)
                self.assertEqual(value, expected)
                if len(timers) >= 2:
                    self.assertEqual(seen, path)

    def test_trim_spaces_preserves_content(self):
        util = NS(GetLength=len, GetNthChar=lambda s, n: s[n] if 0 <= n < len(s) else '',
                  SubString=lambda s, start, length=0: s[start:] if length == 0 else s[start:start + length])
        for text in ('', ' ', '   ', 'abc', 'abc ', ' abc', '  abc  ', 'a b', ' a b '):
            with self.subTest(text=text):
                value, _ = call('sslUtility', 'Trim', dict(var=text, StringUtil=util))
                self.assertEqual(value, text.strip(' '))

    def test_removing_items_handles_duplicates_and_prevent_all(self):
        a, b, c = object(), object(), object()
        for entries, removing, prevent in itertools.product(
            ([], [a], [a, a], [a, b], [a, a, b], [a, b, c], [None, a]),
            ([], [a], [a, a], [b], [a, b, c], [None]), (False, True)):
            with self.subTest(entries=entries, removing=removing, prevent=prevent):
                expected = [entry for entry in entries if entry not in removing]
                if not entries or not removing or (prevent and not expected):
                    expected = entries
                result, _ = call('sslUtility', 'RemoveDupesFromList',
                                 dict(List=Array(entries), Removing=Array(removing), PreventAll=prevent,
                                      sslUtility=NS(AnimationArray=lambda n: Array([None] * n))))
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main(argv=[sys.argv[0]], verbosity=2)
