"""Exercise production stage selection and public legacy queries with Papyrus stand-ins."""
import unittest

from full_review_papyrus_1111 import Array, NS, call, engine


class StageTimer(unittest.TestCase):
    def test_stale_scene_selection_and_hook_cannot_touch_replacement(self):
        for accepted in (False, True):
            env = dict(asNewScene="new", asStage="target", aiRevision=1, PlaybackRevision=1,
                       SexLabRegistry=NS(StageExists=lambda *_: True),
                       _animationSyncPending=False, _sceneResetSyncPending=False,
                       _Positions=Array(), _StageHistory=Array(), GetActiveScene=lambda: "before",
                       UnregisterForUpdate=lambda: None, AddExperience=lambda *_: None,
                       RegisterForSingleUpdate=lambda _: self.fail("registered for replacement"),
                       SortAliasesToPositions=lambda: self.fail("sorted replacement aliases"))
            env["IsCurrentPlayback"] = lambda revision: revision == env["PlaybackRevision"]
            def select(_):
                env.update(PlaybackRevision=2, _animationSyncPending=True, _sceneResetSyncPending=True)
                return accepted
            env["SetActiveScene"] = select
            self.assertFalse(call("sslThreadModel", "ResetSceneAtStage", env)[0])
            self.assertTrue(env["_animationSyncPending"] and env["_sceneResetSyncPending"])

        for boundary in ("hook", "advance"):
            env = dict(PlaybackRevision=1, asNextStageId="target", asHistory=Array(), GetActiveStage=lambda: "old",
                       Config=NS(HOOKID_STAGESTART=1), SendThreadEvent=lambda _: None)
            env["IsCurrentPlayback"] = lambda revision: revision == env["PlaybackRevision"]
            def change():
                env.update(PlaybackRevision=2, _StageHistory=Array(["replacement"]))
            def hook(_):
                if boundary == "hook":
                    change()
            def advance(*_):
                self.assertEqual(boundary, "advance")
                change()
                return Array(["stale"])
            env.update(RunHook=hook, AdvanceScene=advance)
            call("sslThreadModel", "StartStage", env)
            self.assertEqual(env["_StageHistory"], ["replacement"])

    def test_search_starts_at_third_stage_and_compares_tag_values(self):
        read = []

        def tags(scene, stage):
            read.append((scene, stage))
            return Array([stage in ("active", "match")])

        env = dict(GetActiveScene=lambda: "old", GetActiveStage=lambda: "active",
                   CheckSpecificStageTags=tags, GetPlayingScenes=lambda: Array(["old", "new"]),
                   SexLabRegistry=NS(GetAllStages=lambda _: Array(["s1", "s2", "match"])),
                   Utility=NS(CreateStringArray=lambda n, v: Array([v] * n)))
        result, _ = call("sslThreadModel", "FindSimilarSceneStage", env)
        self.assertEqual(result, ["new", "match"])
        self.assertEqual(read, [("old", "active"), ("new", "match")])

    def test_exhausted_timer(self):
        for name, candidate, accepted, stale, expected in (
            ("found", ["new", "branch"], True, False, [("new", "branch", 7)]),
            ("empty", ["", ""], False, False, ["restart"]),
            ("reset refused", ["new", "branch"], False, False, [("new", "branch", 7), "restart"]),
            ("slot reused", ["new", "branch"], True, True, []),
            ("scene changed", ["new", "branch"], True, False, []),
        ):
            with self.subTest(name=name):
                effects = []
                active = ["old"]
                env = dict(PlaybackRevision=7, ThreadWaitsForOrgasm=lambda: True, _animationSyncPending=False,
                           GetActiveScene=lambda: active[0], GetActiveStage=lambda: "stage",
                           IsCurrentPlayback=lambda rev: rev == env["PlaybackRevision"],
                           ReStartTimer=lambda: effects.append("restart"))

                def find():
                    if stale:
                        env["PlaybackRevision"] += 1
                    if name == "scene changed":
                        active[0] = "other"
                    return Array(candidate)

                def reset(*args):
                    effects.append(args)
                    return accepted

                env.update(FindSimilarSceneStage=find, ResetSceneAtStage=reset)
                call("sslThreadModel", "AdvanceFromTimer", env)
                self.assertEqual(effects, expected)

    def test_direct_stage_reset_uses_exact_stage_and_its_strips(self):
        for stale in (False, True):
            observed = []
            current = ["old"]
            def change(scene):
                current[0] = scene
                return True
            def experience(*args):
                if stale:
                    env["PlaybackRevision"] += 1
            env = dict(asNewScene="new", asStage="branch-B", aiRevision=3, PlaybackRevision=3,
                       IsCurrentPlayback=lambda rev: rev == env["PlaybackRevision"], _animationSyncPending=False,
                       _Positions=Array([1]), _StageHistory=Array(["previous"]),
                       AddExperience=experience, GetActiveScene=lambda: current[0], SetActiveScene=change,
                       UnregisterForUpdate=lambda: None, SortAliasesToPositions=lambda: None,
                       ActorAlias=Array([NS(TryLockAndUnpause=lambda: None,
                                            ResetPosition=lambda *args: observed.append(args))]),
                       SexLabRegistry=NS(StageExists=lambda *_: True, GetStripDataA=lambda scene, stage: Array([stage]), GetPositionSexA=lambda _: Array([1])),
                       Utility=NS(CreateStringArray=lambda *_: Array()), StartStage=lambda history, stage: observed.append(stage))
            ok, _ = call("sslThreadModel", "ResetSceneAtStage", env)
            self.assertEqual(ok, not stale)
            self.assertEqual(observed, [] if stale else [("branch-B", 1), "branch-B"])

    def test_invalid_exact_stage_preserves_pending_state_and_existing_timer(self):
        env = dict(asNewScene="known", asStage="missing", aiRevision=3, _animationSyncPending=False,
                   _sceneResetSyncPending=False, SexLabRegistry=NS(StageExists=lambda *_: False),
                   UnregisterForUpdate=lambda: self.fail("invalid stage cancelled timer"))
        ok, _ = call("sslThreadModel", "ResetSceneAtStage", env)
        self.assertFalse(ok)
        self.assertFalse(env["_animationSyncPending"] or env["_sceneResetSyncPending"])


class LegacyQueries(unittest.TestCase):
    def test_unavailable_actor_thread_ids(self):
        for idx in (-1, 0, 1):
            result, _ = call("sslThreadSlots", "GetThread", dict(aiThreadID=idx, Threads=Array(["a"])))
            self.assertEqual(result, "a" if idx == 0 else None)

    def test_thread_scan_stops_at_active_slot(self):
        class Unexpected:
            @property
            def IsLocked(self):
                raise AssertionError("queried a slot after an active slot")
        for slots, expected in (([NS(IsLocked=False), NS(IsLocked=True), Unexpected()], True), ([], False)):
            value, _ = call("sslThreadSlots", "IsRunning", dict(Threads=Array(slots)))
            self.assertIs(value, expected)

    def test_race_key_and_editor_id(self):
        keys = Array(["first", "meta"])
        for race, key, expected in (("known", "first", True), ("known", "meta", True),
                                    ("known", "other", False), ("missing", "first", False)):
            env = dict(RaceID=race, RaceKey=key, GetRaceByEditorID=lambda name: "known" if name == "known" else None,
                       GetAllRaceKeys=lambda target=None: keys)
            # Papyrus treats a missing form as false for a bool return.
            body = engine["body"]("sslCreatureAnimationSlots", "HasRaceID").replace("Race target =", "target =")
            result, _ = engine["execute"](body, env)
            self.assertEqual(bool(result), expected)
            present, _ = call("sslCreatureAnimationSlots", "HasRaceKey", env)
            self.assertEqual(present, key in keys)

    def test_pick_uses_limit_and_proxy_order(self):
        ids = Array(["unknown", "B", "A", "B"])
        for limit, expected in ((0, []), (1, ["B"]), (2, ["B", "A"]), (4, ["B", "A", "B"])):
            proxies = Array(["A", "B"])
            env = dict(Limit=limit, Aggressive=False, Positions=Array(["actor"]),
                       sslUtility=NS(AnimationArray=lambda n: Array([None] * n)),
                       PickByActorsImpl=lambda *_: ids)
            def convert(candidates, bound):
                local = dict(asSceneIDs=candidates, aiLimit=bound, _proxyid=proxies,
                             SyncBackEnd=lambda: None, GetNthAlias=lambda i: proxies[i],
                             sslUtility=env["sslUtility"], PapyrusUtil=NS(ClampInt=lambda x, a, b: max(a, min(x, b))),
                             FindProxyIndices=lambda slots, keys, maximum: Array([slots.index(k) for k in keys if k in slots][:maximum]))
                return call("sslAnimationSlots", "AsLimitedBaseAnimation", local)[0]
            env["AsLimitedBaseAnimation"] = convert
            result, _ = call("sslAnimationSlots", "PickByActors", env)
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
