"""Production Papyrus control flow against deterministic lifecycle and device stand-ins."""
from types import SimpleNamespace as NS
import re
import unittest
from unittest.mock import patch

import papyrus_harness as harness
from papyrus_harness import Array


def helper(*args, **kwargs):
    original = harness.body
    def body(script, name):
        value = re.sub(r'(?im)^(\s*)Sound ', r'\1Form ', original(script,name))
        return re.sub(r'\s+as\s+(Actor|sslThreadController)\b', '', value, flags=re.I)
    with patch.object(harness, 'body', body):
        return harness.helper(*args, **kwargs)


class LifecycleContracts(unittest.TestCase):
    def test_backwards_stage_preserves_history_prefix(self):
        played = []
        fn = helper('sslThreadModel', 'GoToStage', 'ToStage', {
            'Stage': 3, '_StageHistory': Array(['root','middle','current']),
            '_Positions': Array(['a']), 'ActorAlias': Array([NS(TryLockAndUnpause=lambda:None)]),
            'Utility':NS(ResizeStringArray=lambda items,count:Array(items[:count])),
            'StartStage':lambda items,target:played.append([*items,target]),
        })
        fn(2)
        self.assertEqual(played, [['root','middle']])

    def test_custom_timers_are_reset_before_reuse(self):
        source = harness.source('sslThreadModel')
        body = re.search(r'(?ims)^Function Initialize\(\)\s*\n(.*?)^EndFunction', source).group(1)
        with patch.object(harness, 'body', lambda *_:body):
            fn = helper('sslThreadModel', 'Initialize', '', {
                'LifecycleRevision': 1, 'self': 'thread', 'ActorAlias':Array(),
                'Config':NS(DisableThreadControl=lambda *_:None), 'CenterAlias':NS(TryToClear=lambda:None),
                'UnregisterForUpdate':lambda:None,'UnregisterForUpdateGameTime':lambda:None,
                'PapyrusUtil':NS(ActorArray=lambda n:Array([None]*n)),
                'Utility':NS(CreateStringArray=lambda n:Array(['']*n),CreateFloatArray=lambda n:Array([0.]*n)),
                'DestroyInstance':lambda:None,'GoToState':lambda *_:None,'STATE_IDLE':'Unlocked','FURNI_ALLOW':1,
                '_CustomTimers':Array([123.]),
            }, state_names=('LifecycleRevision','_CustomTimers'))
        fn()
        self.assertEqual(fn.__globals__['_CustomTimers'], [])

    def test_position_callback_updates_the_correct_actor_role(self):
        class Positions(Array):
            @property
            def Length(self):
                return len(self)
        updated=[]
        aliases=Array([NS(GetReference=lambda actor=actor:actor, TryLockAndUnpause=lambda:None,
            ResetPosition=lambda strip,sex,actor=actor:updated.append((actor,strip,sex))) for actor in ('a','b')])
        native=Positions(['b','a'])
        sorter=helper('sslThreadModel','SortAliasesToPositions','',{
            'GetPositions':lambda:native,'ActorAlias':aliases,'_Positions':Positions(['a','b']),
        },state_names=('_Positions',))
        fn=helper('sslThreadModel','OnPositionsChanged','',{
            'LifecycleRevision':3,'IsCurrentSceneRequest':lambda rev:rev==3,
            'GetPositions':lambda:native,'ActorAlias':aliases,'_Positions':Positions(['a','b']),
            'GetActiveScene':lambda:'scene','GetActiveStage':lambda:'stage',
            'SexLabRegistry':NS(GetStripDataA=lambda *_:Array([7,9]),GetPositionSexA=lambda *_:Array([1,2])),
        })
        def sort_and_publish():
            sorter()
            fn.__globals__['_Positions']=sorter.__globals__['_Positions']
        fn.__globals__['SortAliasesToPositions']=sort_and_publish
        fn()
        self.assertEqual(updated,[('b',7,1),('a',9,2)])

    def test_preselected_strapon_survives_preparation(self):
        source=harness.source('sslActorAlias')
        body=re.search(r'(?ims)^\s*Event OnDoPrepare\([^\n]+\)\s*\n(.*?)^\s*EndEvent',source).group(1)
        actor=NS(GetAnimationVariableInt=lambda *_:1,GetAnimationVariableBool=lambda *_:False)
        with patch.object(harness,'body',lambda *_:body):
            fn=helper('sslActorAlias','OnDoPrepare','asEventName, asStringArg, afNumArg, akPathTo',{
                '_Thread':NS(tid=1,PrepareDone=lambda:None),
                'UnregisterForModEvent':lambda *_:None,'WaitForPathToCenter':lambda *_:None,'GoToState':lambda *_:None,
                '_ActorRef':actor,'_sex':1,'STATE_PAUSED':'Paused','_Strapon':'selected','_HadStrapon':None,
                '_Config':NS(FemaleVoiceDelay=4,WornStrapon=lambda *_:None,GetStrapon=lambda:'random',DebugMode=False),
            },state_names=('_Strapon','_HadStrapon'))
        fn('prepare','',0,None)
        self.assertEqual(fn.__globals__['_Strapon'],'selected')

    def test_settling_scene_change_keeps_timer_registration(self):
        scheduled = [True]
        reset = helper('sslThreadModel', 'ResetScene', 'asNewScene', {
            'LifecycleRevision': 1, 'SexLabUtil': NS(GetCurrentGameRealTime=lambda: 0),
            '_sceneResetSyncPending': False, '_nextSceneResetAt': 1,
            'Log': lambda *_: None,
        }, state_names=('_sceneResetSyncPending',))
        pick = helper('sslThreadController', 'PickRandomScene', 'asNewScene', {
            'GetPlayingScenes': lambda: Array(['old', 'new']),
            'GetActiveScene': lambda: 'old', 'ResetScene': reset,
            'UnregisterForUpdate': lambda: scheduled.__setitem__(0, False),
            'Log': lambda *_: None, 'SendThreadEvent': lambda *_: None,
        })
        pick('new')
        self.assertTrue(scheduled[0])

    def test_stale_branch_choice_is_ignored(self):
        called = []
        fn = helper('sslThreadModel', 'BranchToCurrent', 'aiBranch, aiRevision, asScene, asStage', {
            'IsCurrentSceneRequest': lambda revision: revision == 3,
            'GetActiveScene': lambda: 'scene', 'GetActiveStage': lambda: 'stage',
            'BranchTo': called.append,
        })
        fn(1, 2, 'scene', 'stage')
        fn(1, 3, 'previous-scene', 'stage')
        fn(1, 3, 'scene', 'previous-stage')
        self.assertEqual(called, [])
        fn(1, 3, 'scene', 'stage')
        self.assertEqual(called, [1])

    def test_graph_skip_and_close_reject_old_lifecycle(self):
        called=[]
        env={
            'IsCurrentSceneRequest':lambda revision:revision==3,
            'GetActiveScene':lambda:'scene','GetActiveStage':lambda:'stage',
            'self':NS(ToggleVisibilitySceneGraph=lambda state:called.append(('close',state))),
            'SkipTo':lambda target:called.append(('skip',target)),
        }
        skip=helper('sslThreadModel','SkipToCurrent','aiRevision, asScene, asOrigin, asTarget',env)
        close=helper('sslThreadModel','CloseSceneGraphCurrent','aiRevision, asScene',env)
        skip(2,'scene','stage','target');close(2,'scene')
        skip(3,'scene','previous-stage','target');close(3,'old-scene')
        self.assertEqual(called,[])
        skip(3,'scene','stage','target')
        self.assertEqual(called,[('close',-1),('skip','target')])

    def test_game_reload_invalidates_both_animation_proxy_caches(self):
        source=harness.source('sslSystemAlias')
        body=re.search(r'(?ims)^Event OnPlayerLoadGame\(\)\s*\n(.*?)^EndEvent',source).group(1)
        invalidated=[]
        with patch.object(harness,'body',lambda *_:body):
            fn=helper('sslSystemAlias','OnPlayerLoadGame','',{
                'Config':NS(CheckSystem=lambda:True,Reload=lambda:None), 'IsInstalled':True,
                'AnimSlots':NS(InvalidateBackEnd=lambda:invalidated.append('human')),
                'CreatureSlots':NS(InvalidateBackEnd=lambda:invalidated.append('creature')),
                'ThreadSlots':NS(StopAll=lambda:None), 'ModEvent':NS(Create=lambda *_:1,Send=lambda *_:None),
            })
        fn()
        self.assertEqual(invalidated,['human','creature'])

    def test_female_aggressor_uses_aggressor_strip_settings(self):
        fn = helper('sslActorLibrary', 'StripActor', 'ActorRef, VictimRef=None, DoAnimate=True, LeadIn=False', {
            'SexLabRegistry': NS(GetSex=lambda *_: 1),
            'sslSystemConfig': NS(GetStripForms=lambda femaleOrVictim, aggressive: [femaleOrVictim, bool(aggressive)]),
            'StripActorImpl': lambda actor, mask, weapons, animate: (mask, weapons),
        })
        self.assertEqual(fn('aggressor', 'victim'), (False, True))
        self.assertEqual(fn('victim', 'victim'), (True, True))
        self.assertEqual(fn('actor'), (True, False))

    def test_victim_redress_policy_is_respected(self):
        for victim in (False, True):
            for redress in (False, True):
                restored = []
                fn = helper('sslActorLibrary', 'UnstripActor', 'ActorRef, Stripped, IsVictim=False', {
                    'Config': NS(RedressVictim=redress),
                    'RestoreStripItem': lambda actor,item: restored.append(item),
                })
                fn('actor', Array(['boots']), victim)
                self.assertEqual(restored, [] if victim and not redress else ['boots'])

    def test_stable_vrik_position_does_not_restart_restore_countdown(self):
        settings = []
        actor = NS(X=10, Y=20, Z=30, GetAngleZ=lambda: 45)
        state = ('_hasPositionVRIK', '_lastPositionXVRIK', '_lastPositionYVRIK', '_lastPositionZVRIK', '_lastAngleVRIK')
        fn = helper('sslSystemConfig', 'UpdatePositioningVRIK', 'VRIKRestoreInTicks', {
            '_bAnimatingVR': True, 'POVModeVR': 1, 'VRIK_FPP_FREE': 1,
            '_hasPositionVRIK': False, '_lastPositionXVRIK': 0, '_lastPositionYVRIK': 0,
            '_lastPositionZVRIK': 0, '_lastAngleVRIK': 0,
            'Game': NS(GetPlayer=lambda: actor),
            'VRIK': NS(VrikSetSetting=lambda key,value:settings.append((key,value))),
        }, state_names=state)
        self.assertEqual(fn(0), 3)
        initial_calls = len(settings)
        self.assertEqual(fn(2), 2)
        self.assertEqual(fn(-1), -1)
        self.assertEqual(len(settings), initial_calls)
        actor.X += 50
        self.assertEqual(fn(0), 3)

    def test_only_player_orgasm_sends_configured_lovense_duration(self):
        for actor in ('player', 'npc'):
            actions = []
            fn = helper('sslActorAlias', 'DoOrgasm', 'Forced=False', {
                '_hasOrgasm': False, '_OrgasmCount': 0, '_Config': NS(OrgasmEffects=True, HasVRIK=False,
                    ShakeStrength=0, OrgasmFX=None, SFXVolume=1, VoiceVolume=1),
                '_ActorRef': actor, '_PlayerRef': 'player', '_sex': 1, 'IsSilent': True,
                '_bEnjEnabled': False, '_FullEnjoyment': 80, '_Thread': NS(tid=2),
                'UnregisterForUpdate': lambda:None, 'RegisterForSingleUpdate':lambda *_:None,
                'UPDATE_INTERVAL':.25, 'PlayLouder':lambda *_:None,
                'SexLabUtil':NS(GetCurrentGameRealTime=lambda:100),
                'sslSystemConfig':NS(GetSettingInt=lambda key:20 if key=='iLovenseStrengthOrgasm' else 0,
                                    GetSettingFlt=lambda key:8.5),
                'sslLovense':NS(IsLovenseInstalled=lambda:True, StartOrgasmAction=lambda strength,duration:actions.append((strength,duration))),
                'ModEvent':NS(Create=lambda *_:1, PushForm=lambda *_:None, PushInt=lambda *_:None, Send=lambda *_:None),
                'TrackedEvent':lambda *_:None, 'TRACK_ORGASM':'Orgasm',
                'GetActorName':lambda:actor, 'Log':lambda *_:None,
            }, state_names=('_hasOrgasm','_OrgasmCount','_FullEnjoyment'))
            fn(True)
            self.assertEqual(actions, [(20,8.5)] if actor=='player' else [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
