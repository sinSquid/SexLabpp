"""Production Papyrus control flow with stand-ins; real PSC compilation is separate."""
from types import SimpleNamespace as NS
from papyrus_harness import Array, helper

allocate = lambda n: Array([None] * n)
push = helper('sslUtility', 'PushAnimation', 'var, Array', {'AnimationArray': allocate})
merge = helper('sslUtility', 'MergeAnimationLists', 'List1,List2', {'PushAnimation': push})
for a,b,expected in [(['A','B'],['B','C'],['A','B','C']),([],['A','A'],['A']),
                      (list(range(127)),[127,128],list(range(128))),([],[],[])]:
    left,right=Array(a),Array(b)
    assert merge(left,right)==expected and left==a and right==b
trim=helper('sslUtility','Trim','var',{'StringUtil':NS(GetLength=len,GetNthChar=lambda s,i:s[i] if 0<=i<len(s) else '',SubString=lambda s,i,n:s[i:i+n])})
for s in ('',' ','  abc  ','a b','abc ',' abc','   '):assert trim(s)==s.strip(' ')
path=Array(['one','branch','terminal'])
stage=helper('sslBaseAnimation','GetStageBounded','aiDepth',{'Registry':'id','SexLabRegistry':NS(GetPathMax=lambda *a:path)})
assert [stage(i) for i in (0,1,2,3,4)]==['one','one','branch','terminal','terminal']
path.clear();assert stage(1)==''
phase_calls=[]
setphase=helper('sslBaseExpression','SetPhase','Phase,Gender,Preset',{'Registry':'id','Female':1,'SetValues':lambda *a:phase_calls.append(a)})
setphase(1,0,Array([0]*32));setphase(2,1,Array([0]*32));setphase(0,0,Array())
assert [c[2] for c in phase_calls]==[0,1]
entries=Array([NS(Registered=True),None,NS(Registered=True),NS(Registered=True)])
selected=helper('sslExpressionSlots','GetList','Valid',{'GetAliases':lambda:entries,
    'sslUtility':NS(ExpressionArray=allocate),'PapyrusUtil':NS(CountBool=lambda a,v:a.count(v))})
assert selected(Array([False,True,True]))==[entries[2],entries[3]]
for name in ('PickByStatus','RandomByTag'):
    options=Array([object()])
    env={'GetByStatus':lambda *a:options,'GetByTag':lambda *a:options,
         'Utility':NS(RandomInt=lambda low,high:high)}
    args='ActorRef,IsVictim,IsAggressor' if name=='PickByStatus' else 'Tag,ForFemale'
    f=helper('sslExpressionSlots',name,args,env)
    assert f(*(None,False,False) if name=='PickByStatus' else ('x',True)) is options[0]
timer=helper('sslThreadModel','GetStageTimer','maxstage',{'Timers':Array([7.5])})
assert timer(0)==7.5
print('PASS: actual merge, trim, stage/phase mapping, filtering, single-entry random and timer')

calls=[]
fields=('_animationSyncPending','_sceneResetSyncPending','_queuedSceneReset','_nextSceneResetAt',
        '_queuedStageScene','_queuedStageID','_animationStarted')
env=dict(_animationSyncPending=True,_sceneResetSyncPending=True,_queuedSceneReset='',
    _nextSceneResetAt=0,_queuedStageScene='new-scene',_queuedStageID='branch-target',
    _queuedStageRevision=4,LifecycleRevision=4,_animationStarted=True,
    SexLabUtil=NS(GetCurrentGameRealTime=lambda:100),SCENE_RESET_SETTLE_TIME=.1,
    GetActiveScene=lambda:'new-scene',GetActiveStage=lambda:'first-stage',
    SexLabRegistry=NS(GetAllStages=lambda _:Array(['first-stage','unrelated','branch-target'])),
    OnStageChangedUpdateHUD=lambda:None,SkipTo=lambda target:calls.append(('skip',target)),
    ConfigureStageTimer=lambda restart:calls.append(('timer',restart)),ConsumeFixedLengthTimerExpiration=lambda:False)
sync=helper('sslThreadModel','OnAnimationSynchronized','',env,fields)
sync();assert calls==[('skip','branch-target')]
sync();assert calls==[('skip','branch-target'),('timer',False)]
calls.clear();sync.__globals__.update(_queuedStageScene='new-scene',_queuedStageID='branch-target',_queuedStageRevision=3)
sync();assert calls==[('timer',False)]
calls.clear()
reset=helper('sslThreadModel','ResetScene','asNewScene',dict(
    LifecycleRevision=2,_sceneResetSyncPending=False,_nextSceneResetAt=0,_animationSyncPending=False,
    SexLabUtil=NS(GetCurrentGameRealTime=lambda:100),Log=lambda *a:None,
    UnregisterForUpdate=lambda:calls.append('unregister'),GetActiveScene=lambda:'old',
    AddExperience=lambda *a:None,_Positions=Array(),_StageHistory=Array(),
    SetActiveScene=lambda _:False,IsCurrentSceneRequest=lambda r:r==2,
    RegisterForSingleUpdate=lambda _:calls.append('register'),ANIMATING_UPDATE_INTERVAL=.5),
    ('_animationSyncPending','_sceneResetSyncPending','_queuedSceneReset'))
assert reset('invalid') is False and calls==['unregister','register']
assert not reset.__globals__['_animationSyncPending']
calls.clear()
move=helper('sslThreadController','MoveScene','',dict(
    LifecycleRevision=2,IsCurrentSceneRequest=lambda r:r==2,
    SexLabRegistry=NS(IsCompatibleCenter=lambda *a:True),GetActiveScene=lambda:'scene',
    Game=NS(GetPlayer=lambda:object()),_bOpenedSceneHUD=False,
    StorageUtil=NS(GetIntValue=lambda *a:0),RepositionInfoMsg=NS(Show=lambda:1),
    UnregisterForUpdate=lambda:calls.append('unregister')))
move();assert calls==[]
print('PASS: actual branch-ID deferred transition, stale queue, failed reset resume and cancelled move timer')
