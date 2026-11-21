"""Run the actual Ending handlers with simulated Papyrus calls."""

import re
import sys
import unittest

from full_review_papyrus_1111 import Array, NS, call, engine, event, source


def ending_reset(name, env):
    ending = source("sslThreadModel").split("State Ending\n", 1)[1].split("\nEndState", 1)[0]
    body = re.search(r"(?ims)^\s*bool Function " + name + r"\([^\n]*\)\s*\n(.*?)^\s*EndFunction", ending)[1]
    return engine["execute"](body, env)[0]


class EndingCleanupTests(unittest.TestCase):
    def test_old_stop_does_not_initialize_reused_slot(self):
        effects = []
        slot = NS(SetupRevision=4, RecycleRevision=2, STATUS_IDLE=0, GetStatus=lambda: 3, GetState=lambda: "Animating",
                  Initialize=lambda: effects.append("reset replacement"))

        def end():
            # A deferred SetTID has recycled the original scene before EndAnimation returns.
            slot.SetupRevision += 1
            slot.RecycleRevision += 1
            effects.append("original recycled")

        slot.EndAnimation = end
        stop = engine["body"]("sslThreadSlots", "StopThread").replace(
            '"Stopping thread " + Slot', '"Stopping thread " + str(Slot)')
        engine["execute"](stop, dict(Slot=slot, sslLog=NS(Log=lambda _: None)))
        self.assertEqual(effects, ["original recycled"])

    def test_stop_survives_startup_of_the_same_slot(self):
        effects = []
        slot = NS(SetupRevision=4, RecycleRevision=2, STATUS_IDLE=0,
                  GetStatus=lambda: 1, GetState=lambda: "Making",
                  EndAnimation=lambda: effects.append("end"), Initialize=lambda: effects.append("reset"))
        def finish_setup(_):
            slot.SetupRevision += 1
        stop = engine["body"]("sslThreadSlots", "StopThread").replace(
            '"Stopping thread " + Slot', '"Stopping thread " + str(Slot)')
        engine["execute"](stop, dict(Slot=slot, sslLog=NS(Log=finish_setup)))
        self.assertEqual(effects, ["end", "reset"])

    def run_ending(self, interrupt=None, quick=False, timer_during_registration=False, setup_from_playback=False):
        trace = []
        actor = object()
        alias = NS(STATE_IDLE="Empty", GetState=lambda: "Empty",
                   GetActorReference=lambda: actor)
        env = dict(
            _QuickResetScenes=quick, _endingCleanupRunning=False, _initializeAfterEnding=False,
            _endingCooldownArmed=False, _setupAliasesAfterEnding=False, id=3, tid="3", self=object(), RecycleRevision=1,
            ActorAlias=Array([alias, NS(STATE_IDLE="Empty", GetState=lambda: "Empty",
                                        GetActorReference=lambda: None,
                                        Clear=lambda: self.fail("empty alias was cleared"))]),
            CancelPendingAnimations=lambda: trace.append("cancel"),
            Config=NS(DisableThreadControl=lambda _: None, HOOKID_END=1,
                      CompletePendingStopNotifications=lambda: None),
            SendModEvent=lambda *_: None, MoveActorsAwayFromPlayer=lambda: None,
            UnregisterCollision=lambda: None, IsObjectiveDisplayed=lambda _: False,
            UpdateAllEncounters=lambda: trace.append("encounters"),
            Utility=NS(Wait=lambda _: self.fail("cleanup waited for event delivery")),
            SendThreadEvent=trace.append, RunHook=lambda _: trace.append("hook"),

            Initialize=lambda: trace.append("recycle"),
        )

        def clear():
            if interrupt:
                interrupt(env)
            self.assertEqual(trace, ["cancel", "encounters"])
            trace.append("clear returned")

        def register(hours):
            trace.append(("cooldown", hours))
            if timer_during_registration:
                event("sslThreadModel", "OnUpdateGameTime", env)
                self.assertEqual(trace[-1], ("cooldown", hours))

        env["RegisterForSingleUpdateGameTime"] = register
        alias.Clear = clear
        def enter_ending():
            event("sslThreadModel", "OnBeginState", env, occurrence=3)

        if setup_from_playback:
            def end_playback():
                env["Initialize"] = lambda: trace.append("recycle")
                enter_ending()

            env.update(Initialize=lambda: call("sslThreadModel", "Initialize", env, occurrence=0),
                       EndAnimation=end_playback)
            call("sslThreadModel", "SetTID", env)
        else:
            enter_ending()
        self.assertFalse(env["_endingCleanupRunning"])
        return trace

    def test_clear_returns_before_end_events(self):
        trace = self.run_ending()
        self.assertEqual(trace, ["cancel", "encounters", "clear returned",
                                 "AnimationEnding", "AnimationEnd", "hook", ("cooldown", 0.1)])

    def test_manual_stop_defers_recycle_without_clearing_again(self):
        def manual_stop(env):
            # The actual StopThread calls Initialize after EndAnimation.
            slot = NS(RecycleRevision=1, STATUS_IDLE=0, GetStatus=lambda: 4, GetState=lambda: "Ending",
                      EndAnimation=lambda: None,
                      Initialize=lambda: call("sslThreadModel", "Initialize", env, occurrence=1))
            stop_thread = engine["body"]("sslThreadSlots", "StopThread").replace(
                '"Stopping thread " + Slot', '"Stopping thread " + str(Slot)')
            engine["execute"](stop_thread, dict(Slot=slot, sslLog=NS(Log=lambda _: None)))
            self.assertTrue(env["_initializeAfterEnding"])

        self.assertEqual(self.run_ending(manual_stop),
                         ["cancel", "encounters", "clear returned",
                          "AnimationEnding", "AnimationEnd", "hook", "recycle"])

    def test_replacement_and_old_timer_cannot_recycle_during_clear(self):
        def try_reuse(env):
            self.assertFalse(ending_reset("ResetAnimation", env))
            self.assertFalse(ending_reset("ResetAnimationQuick", env))
            event("sslThreadModel", "OnUpdateGameTime", env)
            self.assertFalse(env["_initializeAfterEnding"])

        self.assertEqual(self.run_ending(try_reuse),
                         ["cancel", "encounters", "clear returned",
                          "AnimationEnding", "AnimationEnd", "hook", ("cooldown", 0.1)])

    def test_due_timer_during_registration_is_honored(self):
        self.assertEqual(self.run_ending(timer_during_registration=True)[-2:],
                         [("cooldown", 0.1), "recycle"])

    def test_set_tid_from_playback_finishes_setup_without_waiting_for_cooldown(self):
        self.assertEqual(self.run_ending(setup_from_playback=True),
                         ["cancel", "encounters", "clear returned",
                          "AnimationEnding", "AnimationEnd", "hook", "recycle"])

    def test_set_tid_during_quick_reset_leaves_transition_to_its_owner(self):
        trace = []
        env = dict(id=3, self=object(), _QuickResetScenes=True, _setupAliasesAfterEnding=False,
                   _initializeAfterEnding=False, Initialize=lambda: trace.append("initialize"))
        call("sslThreadModel", "SetTID", env)
        self.assertEqual(trace, [])
        self.assertTrue(env["_setupAliasesAfterEnding"])
        self.assertTrue(env["_initializeAfterEnding"])
        env.update(_endingCleanupRunning=False, SetupRevision=3, self=NS(ToggleVisibilitySceneHUD=lambda _: None),
                   UnregisterForUpdateGameTime=lambda: None, _Positions=Array(), asTagString="",
                   GetSubmissives=lambda: Array(), _furniStatus=0, CenterRef=None,
                   SexLabRegistry=NS(LookupScenesA=lambda *_: Array(["new"]), GetCommonTags=lambda _: Array(),
                                     GetSceneName=str), Log=lambda *_: None,
                   DestroyInstance=lambda preserve: None, STATE_SETUP="Making", STATE_PLAYING="Animating",
                   GoToState=trace.append, SetScenes=lambda _: None, StartThread=lambda: True,
                   GetPrimaryScenes=lambda: Array(["new"]), GetActiveScene=lambda: "new",
                   Utility=NS(CreateStringArray=lambda _: Array()), StartStage=lambda *_: None)
        self.assertFalse(ending_reset("ResetAnimationQuick", env))
        self.assertEqual(trace, ["Making", "Animating", "initialize"])
        self.assertFalse(env["_QuickResetScenes"])

    def test_set_tid_defers_alias_setup_until_clear_returns(self):
        def reinitialize(env):
            for alias in env["ActorAlias"]:
                alias.Setup = lambda: self.fail("SetTID touched aliases during Clear")
            finish = env["Initialize"]
            env["Initialize"] = lambda: call("sslThreadModel", "Initialize", env, occurrence=1)
            call("sslThreadModel", "SetTID", env)
            self.assertTrue(env["_setupAliasesAfterEnding"])
            self.assertTrue(env["_initializeAfterEnding"])

            tail = []
            for alias in env["ActorAlias"]:
                alias.Setup = lambda: tail.append("setup")
                alias.Initialize = lambda: self.fail("alias initialized twice")
            noop = lambda *_: None
            env.update(SetupRevision=3, STATE_IDLE="Unlocked", FURNI_ALLOW=0,
                       Utility=NS(CreateFloatArray=lambda _: Array(), CreateStringArray=lambda _: Array()),
                       PapyrusUtil=NS(ActorArray=lambda _: Array()), CenterAlias=NS(TryToClear=noop),
                       UnregisterForUpdate=noop, UnregisterForUpdateGameTime=noop,
                       DestroyInstance=lambda: tail.append("destroy"), GoToState=tail.append)

            def finish_deferred():
                call("sslThreadModel", "Initialize", env, occurrence=1)
                self.assertEqual(tail, ["setup", "setup", "destroy", "Unlocked"])
                finish()

            env["Initialize"] = finish_deferred

        self.assertEqual(self.run_ending(reinitialize)[-2:], ["hook", "recycle"])

    def test_failed_quick_restart_leaves_already_recycled_slot_alone(self):
        states = []
        env = dict(_endingCleanupRunning=False, _QuickResetScenes=True, SetupRevision=4,
                   self=NS(ToggleVisibilitySceneHUD=lambda _: None), _Positions=Array(),
                   GetSubmissives=lambda: Array(), _furniStatus=0, CenterRef=None, asTagString="",
                   SexLabRegistry=NS(LookupScenesA=lambda *_: Array(["new"])),
                   UnregisterForUpdateGameTime=lambda: None, DestroyInstance=lambda _: None,
                   GoToState=states.append, SetScenes=lambda _: None, STATE_SETUP="Making", STATE_END="Ending")

        def failed_start():
            # StartThread increments SetupRevision; its failure path calls Initialize.
            env.update(SetupRevision=6, _QuickResetScenes=False)
            states.append("Unlocked")
            return None

        env.update(StartThread=failed_start, GetState=lambda: states[-1])
        self.assertFalse(ending_reset("ResetAnimationQuick", env))
        self.assertEqual(states, ["Making", "Unlocked"])

    def test_stop_and_load_notifications_wait_for_actual_slot_return(self):
        for load, reuse in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(load=load, reuse=reuse):
                notifications = []
                def during_clear(env):
                    slot = NS(RecycleRevision=1, STATUS_IDLE=0, GetStatus=lambda: 4, GetState=lambda: "Ending",
                              EndAnimation=lambda: None,
                              IsEndingRecyclePending=lambda: call(
                                  "sslThreadModel", "IsEndingRecyclePending", env)[0],
                              Initialize=lambda: call("sslThreadModel", "Initialize", env, occurrence=1))
                    stop = engine["body"]("sslThreadSlots", "StopThread").replace(
                        '"Stopping thread " + Slot', '"Stopping thread " + str(Slot)')
                    events = NS(Create=lambda name: name, Send=notifications.append)
                    recycled = NS(RecycleRevision=1, STATUS_IDLE=0, GetStatus=lambda: 0, Initialize=lambda: None,
                                  IsEndingRecyclePending=lambda: False)
                    participants = [slot, recycled] if reuse else [slot]
                    slots = dict(Threads=Array(participants), ModEvent=events,
                                 StopThread=lambda target: engine["execute"](
                                     stop, dict(Slot=target, sslLog=NS(Log=lambda _: None))),
                                 _stopNotificationsPending=False, _loadNotificationPending=False,
                                 _stopRequestsInProgress=0, _stopRequestRevision=0,
                                 _sendingStopNotifications=False)
                    slots["CompletePendingStopNotifications"] = lambda: call(
                        "sslThreadSlots", "CompletePendingStopNotifications", slots)

                    def request(game_load):
                        slots["abGameLoad"] = game_load
                        call("sslThreadSlots", "RequestStopAll", slots)

                    slots["RequestStopAll"] = request
                    stop_all = lambda: call("sslThreadSlots", "StopAll", slots)
                    if load:
                        event("sslSystemAlias", "OnPlayerLoadGame", dict(
                            Config=NS(CheckSystem=lambda: True, Reload=lambda: None),
                            IsInstalled=True, ModEvent=events,
                            ThreadSlots=NS(StopAll=stop_all, StopAllOnGameLoad=lambda: call(
                                "sslThreadSlots", "StopAllOnGameLoad", slots))))
                    else:
                        stop_all()
                    self.assertEqual(notifications, [])
                    if reuse:
                        recycled.GetStatus = lambda: 3
                    noop = lambda *_: None
                    for alias in env["ActorAlias"]:
                        alias.Initialize = noop
                    env["Config"].CompletePendingStopNotifications = slots["CompletePendingStopNotifications"]

                    def return_to_pool(state):
                        self.assertEqual(state, "Unlocked")
                        self.assertEqual(notifications, [])
                        slot.GetStatus = lambda: 0

                    env.update(SetupRevision=3, STATE_IDLE="Unlocked", FURNI_ALLOW=0,
                               Utility=NS(CreateFloatArray=lambda _: Array(), CreateStringArray=lambda _: Array()),
                               PapyrusUtil=NS(ActorArray=lambda _: Array()), CenterAlias=NS(TryToClear=noop),
                               UnregisterForUpdate=noop, UnregisterForUpdateGameTime=noop,
                               DestroyInstance=lambda: self.assertTrue(slot.IsEndingRecyclePending()),
                               GoToState=return_to_pool,
                               Initialize=slot.Initialize)

                self.run_ending(during_clear)
                expected = ["SexLabStoppedActive"]
                if load:
                    expected.append("SexLabGameLoaded")
                self.assertEqual(notifications, expected)

    def test_new_stop_request_invalidates_in_flight_notifications(self):
        for boundary in ("scan", "create", "send", "load_create"):
            with self.subTest(boundary=boundary):
                notices = []
                inject = True
                first = NS(IsEndingRecyclePending=lambda: False)
                second = NS(pending=False)
                second.IsEndingRecyclePending = lambda: second.pending

                def invoke(method, **kwargs):
                    # Reentrant Papyrus functions keep separate invocation locals.
                    saved = {name: slots.get(name) for name in
                             ("i", "revision", "handle", "loadHandle", "notifyLoad", "abGameLoad")}
                    try:
                        slots.update(kwargs)
                        call("sslThreadSlots", method, slots)
                    finally:
                        slots.update(saved)

                def overlap():
                    nonlocal inject
                    if inject:
                        inject = False
                        invoke("RequestStopAll", abGameLoad=True)

                def check():
                    if boundary == "scan":
                        overlap()
                    return False

                def create(name):
                    if (boundary, name) in (("create", "SexLabStoppedActive"),
                                            ("load_create", "SexLabGameLoaded")):
                        overlap()
                    return name

                def send(name):
                    self.assertFalse(second.pending, "notification sent before new stop completed")
                    notices.append(name)
                    if boundary == "send" and name == "SexLabStoppedActive":
                        overlap()

                first.IsEndingRecyclePending = check
                slots = dict(Threads=Array([first, second]), _stopRequestsInProgress=0,
                             _stopRequestRevision=1, _sendingStopNotifications=False,
                             _stopNotificationsPending=True, _loadNotificationPending=True,
                             StopThread=lambda slot: setattr(slot, "pending", True),
                             ModEvent=NS(Create=create, Send=send, Release=lambda _: None),
                             CompletePendingStopNotifications=lambda: invoke("CompletePendingStopNotifications"))
                invoke("CompletePendingStopNotifications")
                expected = ["SexLabStoppedActive"] if boundary in ("send", "load_create") else []
                self.assertEqual(notices, expected)
                self.assertTrue(second.pending)
                second.pending = False
                invoke("CompletePendingStopNotifications")
                invoke("CompletePendingStopNotifications")
                self.assertEqual(notices, [*expected, "SexLabStoppedActive", "SexLabGameLoaded"])

    def test_quick_reset_skips_ending_cleanup(self):
        self.assertEqual(self.run_ending(quick=True), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
