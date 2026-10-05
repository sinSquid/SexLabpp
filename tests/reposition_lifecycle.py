"""Actual script reposition/actor capture paths with scheduler/API stand-ins."""
from types import SimpleNamespace as NS
import full_sixth_scripts as psc
from full_sixth_scripts import helper, Array
for stop_at in (None,1,2,15,61,62,75,'center'):
    status=[1];request=[7];waits=[];movements=[];centers=[];calls=[]
    class Player:
        X=Y=Z=0.
    player=Player()
    def wait(seconds):
        waits.append(seconds);player.X+=1
        assert len(waits)<=82, 'unbounded reposition wait'
        if len(waits)==stop_at:
            status[0]=0
            move.__globals__['StartupRequest']=8
    alias=NS(STATE_PAUSED='Paused',GoToState=lambda state:calls.append('pause'),TryPauseAndUnlock=lambda:calls.append('unlock'),TryLockAndUnpause=lambda:calls.append('lock'))
    move=helper('sslThreadController','MoveScene','',{
        'StartupRequest':7,'STATUS_INSCENE':1,'GetStatus':lambda:status[0],
        'SexLabRegistry':NS(IsCompatibleCenter=lambda *args:True),
        'GetActiveScene':lambda:'scene','Game':NS(GetPlayer=lambda:player),
        '_bOpenedSceneHUD':False,'_bFocusedSceneHUD':True,'HasPlayer':True,
        'StorageUtil':NS(GetIntValue=lambda *args:1),
        'UnregisterForUpdate':lambda:None,'Positions':Array([player]),
        'ActorAlias':Array([alias]),'PlayerRef':player,
        'SexLabUtil':NS(SetActorMovement=lambda actor,mode:movements.append(mode)),
        'Utility':NS(Wait=wait),'Input':NS(IsKeyPressed=lambda key:False),'Config':NS(MoveScene=12),
        'CenterOnObject':lambda actor:centers.append(actor)
    })
    # Papyrus permits the same ActorAlias name for an array property and helper;
    # provide an object with both capabilities.
    class Aliases(Array):
        def __call__(self,actor):return self[0]
    move.__globals__['ActorAlias']=Aliases([alias])
    if stop_at=='center':
        def center(actor):
            centers.append(actor);move.__globals__['StartupRequest']=8
        move.__globals__['CenterOnObject']=center
    move()
    if stop_at=='center':assert centers==[player] and move.__globals__['_bFocusedSceneHUD'] is True
    elif stop_at is None:assert len(waits)==82 and centers==[player] and calls[-1]=='lock'
    else:
        assert len(waits)==stop_at and not centers and 'lock' not in calls
        if stop_at<=61:assert movements==[1]
# Actor aliases capture graph state when claimed, before native recovery mutates it.
original={'IsNPC':1,'bHumanoidFootIKDisable':False};states=[]
actor=NS(IsDead=lambda:False,IsUnconscious=lambda:False,
 GetAnimationVariableInt=lambda name:original[name],GetAnimationVariableBool=lambda name:original[name],SetFactionRank=lambda *args:None)
claim=helper('sslActorAlias','SetActor','ProspectRef',{
 'ForceRefTo':lambda actor:None,'SexLabRegistry':NS(GetSex=lambda *args:0,GetRaceID=lambda *args:0),
 'LIVESTATUS_DEAD':1,'LIVESTATUS_UNCONSCIOUS':2,'LIVESTATUS_ALIVE':0,
 '_AnimatingFaction':object(),'TRACK_ADDED':'Added','TrackedEvent':lambda *args:None,
 'GoToState':lambda state:states.append(state),'STATE_SETUP':'Ready'},
 state_names=('_ActorRef','_livestatus','_sex','_raceID','_AnimVarIsNPC','_AnimVarbHumanoidFootIKDisable'))
assert claim(actor)
original.update(IsNPC=0,bHumanoidFootIKDisable=True)
assert claim.__globals__['_AnimVarIsNPC']==1 and claim.__globals__['_AnimVarbHumanoidFootIKDisable'] is False
print('PASS: actual reposition wait is bounded, stale continuations stop; alias captures graph state before native recovery')

# Actual Ending.OnBeginState: bound failed cleanup and stop stale latent continuations.
import re
text=psc.source('sslThreadModel').split('State Ending',1)[1]
body=re.search(r'Event OnBeginState\(\)(.*?)EndEvent',text,re.S|re.I)[1]
body=body.replace('self as sslThreadController','self') # Type cast only; stand-in has no VM type system.
original_source=psc.source
try:
    psc.source=lambda _: 'Function selected()\n'+body+'EndFunction'
    for scenario in ('idle','timeout','stale'):
        calls=[];waits=[]
        alias=NS(STATE_IDLE='Empty',GetState=lambda:'Empty' if scenario=='idle' else 'Ready')
        def wait(seconds):
            waits.append(seconds)
            if scenario=='stale':ending.__globals__['StartupRequest']=2
        env={'self':object(),'_QuickResetScenes':False,'StartupRequest':1,'STATE_END':'Ending','GetState':lambda:'Ending',
             'ActorAlias':Array([None,alias]),'tid':0,'Utility':NS(Wait=wait),
             'Config':NS(DisableThreadControl=lambda *a:None,HOOKID_END=1),
             'IsObjectiveDisplayed':lambda *a:False,'Log':lambda *a:calls.append('timeout'),
             'SendThreadEvent':lambda name:calls.append(name),'RunHook':lambda *a:calls.append('hook'),
             'RegisterForSingleUpdateGameTime':lambda t:calls.append('schedule')}
        for name in ('CancelPendingAnimations','SendModEvent','MoveActorsAwayFromPlayer','UnregisterCollision','UpdateAllEncounters'):env[name]=lambda *a:None
        ending=helper('','selected','',env);ending()
        if scenario=='idle':assert not waits and calls==['AnimationEnding','AnimationEnd','hook','schedule']
        elif scenario=='timeout':assert len(waits)==200 and calls==['timeout','schedule']
        else:assert len(waits)==1 and not calls
finally:psc.source=original_source
print('PASS: actual Ending wait bounds failed cleanup, skips empty aliases and rejects stale continuations')

for initially_essential in (False,True):
    essential=[initially_essential];killed=[]
    base=NS(SetEssential=lambda flag:essential.__setitem__(0,flag))
    actor=NS(IsEssential=lambda:essential[0],GetActorBase=lambda:base,
             KillSilent=lambda killer:killed.append(essential[0]),SetFactionRank=lambda *args:None)
    clear=helper('sslActorAlias','Clear','',{
        'GetIsDead':lambda:True,'_ActorRef':actor,'_killer':None,'_AnimatingFaction':None,
        '_Thread':NS(UpdateAnimatingActorMovement=lambda actor:None),'Parent':NS(Clear=lambda:None)})
    clear();assert killed==[False] and essential[0]==initially_essential
print('PASS: actual dead-alias cleanup restores the shared actor-base essential flag')
