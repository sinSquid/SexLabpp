"""Review-only behavioral probes against production Papyrus helper bodies.

Run with Python 3 from any directory. Initially failed against reviewed HEAD.
Uses the repository's limited Papyrus translator; this is not a VM/engine test.
No production files are changed and no game configuration is touched.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from papyrus_harness import Array, helper


def array(n, value=None):
    return Array([value] * n)


class ObjectContractProbes(unittest.TestCase):
    def test_race_membership_accepts_first_and_rejects_missing(self):
        fn = helper("sslBaseAnimation", "CountValidRaceKey", "RaceKeys", {
            "GetRaceTypes": lambda: Array(["Wolves", "Bears"]),
        })
        self.assertEqual([fn(Array([key])) for key in ("Wolves", "Bears", "Missing")], [1, 1, 0])

    def test_first_creature_race_key_is_supported(self):
        fn = helper("sslCreatureAnimationSlots", "HasRaceKey", "RaceKey", {
            "GetAllRaceKeys": lambda: Array(["FirstCreature", "SecondCreature"]),
        })
        self.assertTrue(fn("FirstCreature"))

    def test_fixed_male_creature_position_is_preserved(self):
        anim = NS(Registry="fixed-male", ActorCount=lambda: 1)
        fn = helper("sslCreatureAnimationSlots", "FilterCreatureGenders",
                    "Anims, MaleCreatures=0, FemaleCreatures=0", {
            "Utility": NS(CreateIntArray=lambda n, value: array(n, value)),
            "SexLabRegistry": NS(GetIsMaleCreaturePositon=lambda *_: True,
                                 GetIsFemaleCreaturePositon=lambda *_: False),
            "PapyrusUtil": NS(RemoveInt=lambda values, value: Array(v for v in values if v != value)),
            "sslUtility": NS(AnimationArray=array),
        })
        self.assertEqual(fn(Array([anim]), 1, 0), [anim])

    def default_tags(self, aggressive, restrict, using_bed=False, supplied=()):
        fn = helper("sslAnimationSlots", "GetByDefaultTags",
                    "Males, Females, IsAggressive, UsingBed, RestrictAggressive, Tags, TagsSuppressed, RequireAll", {
            "SexLabUtil": NS(MergeSplitTags=lambda *_: Array(supplied)),
            "PapyrusUtil": NS(PushString=lambda a, s: Array([*a, s]),
                              ClearEmpty=lambda a: Array(v for v in a if v)),
            "AsBaseAnimation": lambda a: a,
            "GetByTypeImpl": lambda _count, _males, _females, tags: tags,
            "GetByType": lambda _: Array(),
        })
        return fn(1, 1, aggressive, using_bed, restrict, "", "", True)

    def test_aggressive_default_does_not_disallow_forced(self):
        tags = self.default_tags(True, True)
        self.assertNotIn("-Forced", tags)
        self.assertIn("Forced", tags)

    def test_bed_filter_replaces_optional_standing(self):
        tags = self.default_tags(False, True, using_bed=True, supplied=("~Standing",))
        self.assertNotIn("~Standing", tags)
        self.assertIn("-Standing", tags)

    def test_one_remaining_slot_is_allocatable(self):
        for script in ("sslVoiceSlots", "sslExpressionSlots"):
            with self.subTest(script=script):
                fn = helper(script, "FindEmpty", "", {
                    "Slotted": 1,
                    "GetNthAlias": lambda index: NS(Registry="") if 0 <= index < 2 else None,
                })
                self.assertEqual(fn(), 1)

    def test_registered_expression_is_bound_before_callback(self):
        aliases = Array([NS(Registry="", GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION="marker")
                         for _ in range(2)])
        register = helper("sslExpressionSlots", "Register", "Registrar", {
            "Registry": Array(), "RegisterLock": False, "FindEmpty": lambda: 1,
            "sslBaseExpression": NS(CreateEmptyProfile=lambda _: True),
            "GetBySlot": lambda index: aliases[index], "GetNthAlias": lambda index: aliases[index],
        }, state_names=("RegisterLock",))
        callbacks = []
        fn = helper("sslExpressionSlots", "RegisterExpression",
                    "Registrar, CallbackForm=None, CallbackAlias=None", {
            "SyncBackend": lambda: None, "GetAliases": lambda: aliases,
            "Register": register, "GetNthAlias": lambda index: aliases[index],
            "sslObjectFactory": NS(SendCallback=lambda name, index, *_: callbacks.append((name, aliases[index].Registry))),
        })
        result = fn("NewProfile")
        self.assertEqual((result.Registry, callbacks), ("NewProfile", [("NewProfile", "NewProfile")]))

    def test_all_matching_voices_are_returned(self):
        voices = {name: NS(Registry=name) for name in ("match-1", "match-2")}
        fn = helper("sslVoiceSlots", "GetAllByTags", "Tags, TagsSuppressed='', RequireAll=True", {
            "SexLabUtil": NS(MergeSplitTags=lambda *_: Array(["Normal"])),
            "GetVoicesByTagsA": lambda *_: Array(voices),
            "SelectVoiceByTagsA": lambda *_: "match-1",  # native API returns one random match
            "GetbyRegistrar": lambda name: voices[name],
            "Registry": Array(voices), "GetNthAlias": lambda index: list(voices.values())[index],
            "Utility": NS(ResizeStringArray=lambda values,n:Array(values[:n])),
            "sslUtility": NS(VoiceArray=array),
        })
        self.assertEqual({voice.Registry for voice in fn("Normal")}, set(voices))

    def test_animation_search_does_not_discard_match_outside_proxy_prefix(self):
        aliases = Array([NS(Registry="a"), NS(Registry="b")])
        fn = helper("sslAnimationSlots", "AsBaseAnimation", "asSceneIDs", {
            "sslLog": NS(Log=lambda *_: None), "sslUtility": NS(AnimationArray=array),
            "SyncBackEnd": lambda: None, "_proxyid": Array(["a", "b"]),
            "Utility": NS(ResizeStringArray=lambda values,n: Array(values[:n])),
            "GetNthAlias": lambda index: aliases[index],
        })
        import papyrus_harness as harness
        if "Function BindSceneProxy" in harness.source("sslAnimationSlots"):
            bind = helper("sslAnimationSlots", "BindSceneProxy", "asScene, asReserved", {
                "_proxyid": fn.__globals__["_proxyid"], "GetNthAlias": lambda index: aliases[index],
                "GetAliases": lambda: aliases, "PapyrusUtil": NS(PushString=lambda values,item:Array([*values,item])),
                "SexLabRegistry": NS(SceneExists=lambda scene: scene in ("a", "b", "c")),
            }, state_names=("_proxyid",))
            fn.__globals__["BindSceneProxy"] = bind
        self.assertEqual([a.Registry for a in fn(Array(["c"]))], ["c"])

    def test_fetch_position_follows_same_path_as_stage_access(self):
        # root -> short sink, root -> long -> end. Longest path has 3 stages.
        def branch(_scene, node, _index):
            return {"": "short", "root": "short", "short": "", "long": "end", "end": ""}[node]
        fn = helper("sslBaseAnimation", "FetchPosition", "Position", {
            "ActorCount": lambda: 1, "GetMaxDepth": lambda: 3, "Registry": "scene",
            "Utility": NS(CreateStringArray=lambda n: array(n, "")),
            "SexLabRegistry": NS(GetAnimationEvent=lambda _s, node, _p: node or "root", BranchTo=branch,
                GetPathMax=lambda *_: Array(["root", "long", "end"])),
            "Log": lambda *_: None,
        })
        self.assertEqual(fn(0), ["root", "long", "end"])

    def test_unused_animation_proxy_is_used_before_eviction(self):
        aliases = Array([NS(Registry="a"), NS(Registry="b"), NS(Registry="")])
        fn = helper("sslAnimationSlots", "BindSceneProxy", "asScene, asReserved", {
            "_proxyid": Array(["a", "b"]), "GetAliases": lambda: aliases,
            "GetNthAlias": lambda index: aliases[index],
            "PapyrusUtil": NS(PushString=lambda values,item:Array([*values,item])),
            "SexLabRegistry": NS(SceneExists=lambda *_:True),
        }, state_names=("_proxyid",))
        fn("c", Array(["c"]))
        self.assertEqual([alias.Registry for alias in aliases], ["a", "b", "c"])

    def test_voice_match_outside_1000_alias_prefix_returns_a_bound_voice(self):
        aliases=Array([NS(Registry=f'voice-{i}', GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION='marker')
                       for i in range(1000)])
        fn=helper('sslVoiceSlots','GetAllByTags',"Tags, TagsSuppressed='', RequireAll=True",{
            'SexLabUtil':NS(MergeSplitTags=lambda *_:Array(['OnlyLastVoice'])),
            'GetVoicesByTagsA':lambda *_:Array(['voice-1000']),
            'SelectVoiceByTagsA':lambda *_:'voice-1000', 'GetbyRegistrar':lambda *_:None,
            'Registry':Array([a.Registry for a in aliases]), 'GetNthAlias':lambda index:aliases[index],
            'sslUtility':NS(VoiceArray=array), 'Utility':NS(ResizeStringArray=lambda values,n:Array(values[:n])),
        })
        self.assertEqual([a.Registry for a in fn('OnlyLastVoice')], ['voice-1000'])

    def test_reload_invalidates_saved_animation_ids_and_clears_old_tail(self):
        aliases=Array([NS(Registry='removed'),NS(Registry='retained'),NS(Registry='old-tail')])
        invalidate=helper('sslAnimationSlots','InvalidateBackEnd','',{
            '_proxyid':Array(['removed','retained','old-tail']),
            'Utility':NS(CreateStringArray=lambda n:Array(['']*n)),
        },state_names=('_proxyid',))
        invalidate()
        sync=helper('sslAnimationSlots','SyncBackEnd','',{
            '_proxyid':invalidate.__globals__['_proxyid'], 'GetAliases':lambda:aliases,
            'CreateProxyArray':lambda *_:Array(['retained','new']), 'GetCrtSpecifier':lambda:0,
        },state_names=('_proxyid',))
        sync()
        self.assertEqual([a.Registry for a in aliases],['retained','new',''])

    def test_name_lookup_includes_new_native_scenes_outside_saved_proxies(self):
        aliases = Array([NS(Registry="a", Name="Old A"), NS(Registry="b", Name="Old B")])
        fn = helper("sslAnimationSlots", "FindByName", "FindName", {
            "CreateProxyArray": lambda *_:Array(["a","b","c"]), "GetCrtSpecifier":lambda:0,
            "GetAliases":lambda:aliases, "SyncBackEnd":lambda:None,
            "SexLabRegistry":NS(GetSceneName=lambda value:{"a":"Old A","b":"Old B","c":"New Scene"}[value]),
            "FindByRegistrar":lambda value:2 if value=="c" else -1,
        })
        self.assertEqual(fn("New Scene"), 2)

    def test_creature_does_not_match_human_animation_position(self):
        fn = helper("sslBaseAnimation", "MatchGender", "Gender, Position", {
            "GetGender": lambda _: 0, "GenderedCreatures": False,
        })
        self.assertFalse(fn(2, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
