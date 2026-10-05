"""Source-derived Papyrus control-flow tests, not a Papyrus compiler or VM."""
from types import SimpleNamespace
import math
import re
from full_sixth_scripts import Array, helper


class Aliases(Array):
    def __call__(self, actor):
        return next((alias for alias in self if alias.actor == actor), None)


class StrictArray(Array):
    def __getitem__(self, index):
        if isinstance(index, int):
            assert 0 <= index < len(self), (index, len(self))
        return super().__getitem__(index)


def stage_history():
    history = StrictArray(['a', 'b', 'c', 'd', 'e'])
    started = []
    jump = helper('sslThreadModel', 'GoToStage', 'ToStage', {
        'Stage': len(history), '_StageHistory': history, '_Positions': Array(),
        'StartStage': lambda previous, stage: started.append([*previous, stage]),
        'Utility': SimpleNamespace(ResizeStringArray=lambda values, count: values[:count]),
    })
    for target in (2, 3, 4):
        jump(target)
        assert started[-1] == history[:target], (target, started[-1])


def stage_timers():
    climax = Array()
    timers = StrictArray([12.0])
    history = Array(['first'])
    get = helper('sslThreadModel', 'GetStageTimer', 'maxstage', {
        'Timers': timers, '_StageHistory': history,
        'SexLabRegistry': SimpleNamespace(GetClimaxingActors=lambda *args: climax),
        'GetActiveScene': lambda: 'scene', 'GetActiveStage': lambda: 'stage',
    })
    assert get(0) == 12.0
    climax.append(0)
    assert get(0) == 12.0
    climax.clear()
    timers.extend([24.0, 36.0, 48.0])
    for count, expected in ((1, 12.0), (2, 24.0), (3, 36.0), (10, 36.0)):
        history.clear()
        history.extend(['stage'] * count)
        assert get(0) == expected, (count, get(0), expected)
    climax.append(0)
    assert get(0) == 48.0


def rejected_scene_reset():
    calls = []
    reset = helper('sslThreadModel', 'ResetScene', 'asNewScene', {
        '_sceneResetSyncPending': False, '_animationSyncPending': False,
        '_nextSceneResetAt': 0, '_Positions': Array(), '_StageHistory': Array(['stage']),
        'ANIMATING_UPDATE_INTERVAL': 0.1,
        'SexLabUtil': SimpleNamespace(GetCurrentGameRealTime=lambda: 1),
        'UnregisterForUpdate': lambda: calls.append('stop'),
        'RegisterForSingleUpdate': lambda interval: calls.append(('resume', interval)),
        'GetActiveScene': lambda: 'current', 'SetActiveScene': lambda scene: False,
        'AddExperience': lambda *args: calls.append('experience'), 'Log': lambda *args: None,
    }, state_names=('_sceneResetSyncPending', '_animationSyncPending', '_queuedSceneReset'))
    assert reset('invalid') is False
    assert calls == ['stop', ('resume', 0.1)], calls
    assert not reset.__globals__['_sceneResetSyncPending']
    assert not reset.__globals__['_animationSyncPending']


def tag_filters():
    tags = {'A', 'B'}
    check = helper('sslThreadModel', 'CheckTags', 'CheckTags, RequireAll, Suppress', {
        'HasTag': lambda tag: tag in tags,
    })
    for query in ([], ['A'], ['C'], ['A', 'B'], ['A', 'C']):
        for require_all in (False, True):
            for suppress in (False, True):
                matched = all(tag in tags for tag in query) if require_all else any(tag in tags for tag in query)
                expected = not any(tag in tags for tag in query) if suppress else matched
                assert check(Array(query), require_all, suppress) == expected, (query, require_all, suppress)


def alias_boundaries():
    pathing = helper('sslActorAlias', 'SetPathing', 'aiPathingFlag', {
        '_PathingFlag': 0, 'PATHING_DISABLE': -1, 'PATHING_FORCE': 1,
        'PapyrusUtil': SimpleNamespace(ClampInt=lambda value, low, high: min(max(value, low), high)),
    }, state_names=('_PathingFlag',))
    for requested, expected in ((1, 1), (-1, -1), (0, 0), (5, 1), (-5, -1)):
        pathing(requested)
        assert pathing.__globals__['_PathingFlag'] == expected


def offset_arrays():
    offset = helper('sslActorAlias', 'OffsetCoords', 'Output, CenterCoords, OffsetBy', {
        'Math': SimpleNamespace(asin=lambda x: math.degrees(math.asin(x)),
                                sin=lambda x: math.sin(math.radians(x)),
                                cos=lambda x: math.cos(math.radians(x))),
    })
    for lengths in ((5, 6, 4), (6, 5, 4), (6, 6, 3), (0, 0, 0)):
        output, center, delta = (StrictArray([0.] * n) for n in lengths)
        original = list(output)
        offset(output, center, delta)
        assert output == original
    output = StrictArray([0.] * 6)
    offset(output, StrictArray([10., 20., 30., 0., 0., 90.]), StrictArray([2., 3., 4., 5.]))
    assert all(abs(a-b) < 1e-9 for a, b in zip(output, [12., 17., 34., 0., 0., 95.]))


def canceled_move():
    calls = []
    move = helper('sslThreadController', 'MoveScene', '', {
        'GetStatus': lambda: 1, 'STATUS_INSCENE': 1, 'StartupRequest': 7,
        'SexLabRegistry': SimpleNamespace(IsCompatibleCenter=lambda *args: True),
        'Game': SimpleNamespace(GetPlayer=lambda: 'player'), 'GetActiveScene': lambda: 'scene',
        '_bOpenedSceneHUD': False, 'UnregisterForUpdate': lambda: calls.append('stop'),
        'StorageUtil': SimpleNamespace(GetIntValue=lambda *args: 0),
        'RepositionInfoMsg': SimpleNamespace(Show=lambda: 1),
    }, state_names=('_bFocusedSceneHUD',))
    move()
    assert calls == [], calls


def registry_sex_flags():
    current = [0]
    env = {'GetPositionSex': lambda *args: current[0],
           'Math': SimpleNamespace(LogicalAnd=lambda value, mask: value & mask)}
    for name, mask in (('GetIsMalePosition', 1), ('GetIsFemalePosition', 2),
                       ('GetIsFutaPositon', 4), ('GetIsCreaturePositon', 24),
                       ('GetIsMaleCreaturePositon', 8), ('GetIsFemaleCreaturePositon', 16)):
        call = helper('SexlabRegistry', name, 'asID, n', env)
        for flags in range(32):
            current[0] = flags
            assert bool(call('scene', 0)) == bool(flags & mask), (name, flags)


def base_object_tags():
    env = {'Tags': Array(), 'PapyrusUtil': SimpleNamespace(
        PushString=lambda a, b: Array([*a, b]), RemoveString=lambda a, b: Array(x for x in a if x != b))}
    has = helper('sslBaseObject', 'HasTag', 'Tag', env)
    assert not has('missing')
    add = helper('sslBaseObject', 'AddTag', 'Tag', env, state_names=('Tags',))
    assert not add('')
    assert add('A')
    assert not add('A')
    remove = helper('sslBaseObject', 'RemoveTag', 'Tag', {'Tags': Array(['A']), **{k:v for k,v in env.items() if k!='Tags'}}, state_names=('Tags',))
    assert not remove('') and not remove('B')
    assert remove('A') and not remove('A')
    enabled = helper('sslBaseObject', '_SetEnabled', 'aSet', {'_enabled': False}, state_names=('_enabled',))
    enabled(True)
    assert enabled.__globals__['_enabled']


def bed_helpers():
    env = {'GetBedType': lambda bed: bed, 'BedType_None': 0, 'BedType_BedRoll': 1,
           'BedType_Single': 2, 'BedType_Double': 3}
    for name, expected in [('IsBedRoll',1), ('IsSingleBed',2), ('IsDoubleBed',3)]:
        call = helper('sslThreadLibrary', name, 'BedRef', env)
        for kind in range(4): assert call(kind) == (kind==expected), (name,kind)
    find = helper('sslThreadLibrary', 'FindBed', 'CenterRef, Radius, IgnoreUsed, IgnoreRef1, IgnoreRef2', {
        'FindBeds': lambda *args: Array(['used','free']), 'IsBedAvailable': lambda bed: bed=='free'})
    assert find(None, 1000, True, None, None)=='free'
    assert find(None, 1000, False, None, None)=='used'


def expression_selection():
    items = StrictArray(['A', 'B', 'C'])
    for name, args, getter in [('PickByStatus','ActorRef, IsVictim, IsAggressor','GetByStatus'),
                               ('RandomByTag','Tag, ForFemale','GetByTag')]:
        pick = helper('sslExpressionSlots', name, args, {
            getter: lambda *args: items, 'Utility': SimpleNamespace(RandomInt=lambda low, high: high)})
        arguments = (None, False, False) if name=='PickByStatus' else ('tag', True)
        assert pick(*arguments)=='C'
        items.clear()
        assert pick(*arguments) is None
        items.extend(['A','B','C'])


def expression_sparse_filter():
    entries = [SimpleNamespace(Registered=True, name='A'), None,
               SimpleNamespace(Registered=False, name='unregistered'),
               SimpleNamespace(Registered=True, name='B'), SimpleNamespace(Registered=True, name='C')]
    get = helper('sslExpressionSlots', 'GetList', 'Valid', {
        'GetAliases': lambda: Array(entries), 'sslUtility': SimpleNamespace(ExpressionArray=lambda n: StrictArray([None]*n)),
        'PapyrusUtil': SimpleNamespace(CountBool=lambda a,v:a.count(v))})
    for flags in ([False,True,False], [True,False,True], [False,False,True], []):
        actual=get(StrictArray(flags))
        expected=[entries[i].name for i,yes in zip([0,3,4],flags) if yes]
        assert [x.name for x in actual]==expected, (flags,actual)


def registration_case(script):
    class Slot:
        GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION = 'marker'
        def __init__(self, id=''): self.Registry = id
        @property
        def Registered(self): return bool(self.Registry) and self.Registry!='marker'
    slots = Array([Slot('B'), None, Slot()])
    profiles = ['B']
    fail = [False]
    created = []
    def create(id):
        created.append(id)
        if fail[0] or id in profiles: return False
        profiles.append(id)
        return True
    env = {'Slotted': 1, 'Registry': Array(profiles), 'RegisterLock': False,
           'GetAliases': lambda: slots, 'GetAllProfileIDs': lambda: Array(sorted(profiles)),
           'GetNthAlias': lambda i: slots[i] if 0<=i<len(slots) else None,
           'GetBySlot': lambda i: slots[i] if 0<=i<len(slots) else None,
           'sslBaseExpression': SimpleNamespace(CreateEmptyProfile=create),
           'sslBaseVoice': SimpleNamespace(InitializeVoiceObject=create),
           'GetAllVoices': lambda *a:Array(sorted(profiles)),
           'Utility': SimpleNamespace(WaitMenuMode=lambda *a:None)}
    find = helper(script, 'FindEmpty', '', env)
    assert find()==2
    sync = helper(script, 'SyncBackend', '', env)
    lookup = helper(script, 'FindByRegistrar', 'Registrar', env)
    register = helper(script, 'Register', 'Registrar',
                      dict(env, FindEmpty=find, SyncBackend=sync, FindByRegistrar=lookup), state_names=('RegisterLock',))
    fail[0] = True
    assert register('A')==-1 and slots[2].Registry==''
    assert not register.__globals__['RegisterLock']
    fail[0] = False
    where = register('A')
    assert where>=0 and slots[where].Registry=='A'
    assert not register.__globals__['RegisterLock']
    assert find()==-1
    assert register('C')==-1 and 'C' not in profiles
    assert register('')==-1


def expression_registration():
    registration_case('sslExpressionSlots')


def voice_registration():
    registration_case('sslVoiceSlots')
    saved=helper('sslVoiceSlots','FindSaved','ActorRef',{'GetSavedVoice':lambda *a:'voice',
        'FindByRegistrar':lambda id:3 if id=='voice' else -1})
    assert saved('actor')==3


def legacy_animation_data():
    path = StrictArray(['first','middle','last'])
    bounded = helper('sslBaseAnimation', 'GetStageBounded', 'aiDepth', {
        'Registry':'scene','SexLabRegistry':SimpleNamespace(GetPathMax=lambda *a:path)})
    for stage, expected in [(-1,'first'),(0,'first'),(1,'first'),(2,'middle'),(3,'last'),(100,'last')]:
        assert bounded(stage)==expected, (stage,bounded(stage))
    path.clear()
    assert bounded(1)==''
    path.extend(['first','middle','last'])
    registry = SimpleNamespace(GetPathMax=lambda *a:path,GetActorCount=lambda *a:2,
        GetStageOffset=lambda scene,stage,n:StrictArray([100*path.Find(stage)+10*n+j for j in range(4)]))
    offsets = helper('sslBaseAnimation','GetAllAdjustments','AdjustKey',{
        'Registry':'scene','SexLabRegistry':registry,'Utility':SimpleNamespace(CreateFloatArray=lambda n:StrictArray([0.]*n)),
        'PapyrusUtil':SimpleNamespace(ClampInt=lambda v,lo,hi:min(max(v,lo),hi))})
    assert offsets('')==[100*s+10*n+j for s in range(3) for n in range(2) for j in range(4)]
    path.clear();path.extend(str(s) for s in range(100))
    large=offsets('');assert len(large)==128
    assert large==[100*s+10*n+j for s in range(16) for n in range(2) for j in range(4)]
    path.clear();path.extend(['first','middle','last'])
    race = helper('sslBaseAnimation','CountValidRaceKey','RaceKeys',{'GetRaceTypes':lambda:Array(['Dogs','Wolves'])})
    assert race(Array(['Dogs','missing','Wolves']))==2
    timer = helper('sslBaseAnimation','GetTimersRunTime','StageTimers',{
        'Registry':'scene','GetMaxDepth':lambda:3,'SexLabRegistry':SimpleNamespace(
            GetStartAnimation=lambda *a:'first',GetPathMax=lambda *a:path,
            GetFixedLength=lambda scene,stage:{'first':0,'middle':20000,'last':30000}[stage],
            BranchTo=lambda scene,stage,n:path[min(path.Find(stage)+1,2)])})
    assert timer(StrictArray([10,11]))==60


def stripping_weapons():
    unequipped, saved = [], {}
    actor = SimpleNamespace(EquipSlot_RightHand=1,EquipSlot_LeftHand=2,
        GetWornForm=lambda *a:None,GetEquippedObject=lambda hand:['left','right'][hand],
        UnequipItemEX=lambda *args:unequipped.append(args))
    call = helper('sslActorLibrary','StripActorImpl','akActor, aiSlots, abStripWeapons, abAnimate',{
        'UnequipSlots':lambda *a:Array(['armor']), 'IsStrippable':lambda item:True,
        'PapyrusUtil':SimpleNamespace(PushForm=lambda a,x:Array([*a,x])),
        'StorageUtil':SimpleNamespace(SetIntValue=lambda form,key,val:saved.update({form:val})),
        'Utility':SimpleNamespace(Wait=lambda *a:None)})
    assert call(actor,0,True,False)==['armor','right','left']
    assert saved=={'right':1,'left':2}
    assert unequipped==[('right',1,False),('left',2,False)]


def creature_filters():
    keys = Array(['Dogs', 'Wolves'])
    has = helper('sslCreatureAnimationSlots', 'HasRaceKey', 'RaceKey', {'GetAllRaceKeys': lambda: keys})
    for key in ['Dogs', 'Wolves', 'missing']:
        assert has(key) == (key in keys)
    import itertools
    flags = {'m': (True, False), 'f': (False, True), 'e': (True, True), 'h': (False, False)}
    for size in range(4):
        for kinds in itertools.product(flags, repeat=size):
            anim = SimpleNamespace(Registry=kinds, ActorCount=lambda:len(kinds))
            call = helper('sslCreatureAnimationSlots', 'FilterCreatureGenders', 'Anims, MaleCreatures, FemaleCreatures', {
                'Utility':SimpleNamespace(CreateIntArray=lambda n,v:StrictArray([v]*n)),
                'SexLabRegistry':SimpleNamespace(GetIsMaleCreaturePositon=lambda scene,n:flags[scene[n]][0],
                    GetIsFemaleCreaturePositon=lambda scene,n:flags[scene[n]][1]),
                'PapyrusUtil':SimpleNamespace(RemoveInt=lambda a,v:Array(x for x in a if x!=v)),
                'sslUtility':SimpleNamespace(AnimationArray=lambda n:StrictArray([None]*n))})
            m,f,e = kinds.count('m'),kinds.count('f'),kinds.count('e')
            for males in range(4):
                for females in range(4):
                    expected = any(m+extra==males and f+e-extra==females for extra in range(e+1))
                    assert bool(call(Array([anim]),males,females))==expected, (kinds,males,females)


def gender_sorting():
    import itertools
    lesser = helper('sslThreadLibrary', 'IsLesserGender', 'i, n, abFemaleFirst', {})
    call = helper('sslThreadLibrary','SortActors','Positions, FemaleFirst',{
        'PapyrusUtil':SimpleNamespace(RemoveActor=lambda a,v:Array(x for x in a if x!=v)),
        'sslActorLibrary':SimpleNamespace(GetSexAll=lambda a:Array(x[0] for x in a)), 'IsLesserGender':lesser})
    for order in itertools.permutations(range(5)):
        actors = Array([(sex, str(sex)) for sex in order]+[(1,'second female'),None])
        for female_first in (True,False):
            rank=lambda a: (1-a[0] if female_first and a[0]<2 else a[0])
            assert call(actors,female_first)==sorted([a for a in actors if a is not None],key=rank)


def expression_units():
    clamp=lambda x,a,b:min(max(x,a),b)
    for name,arg in [('ToIntArray','FloatArray'),('ToFloatArray','IntArray')]:
        call=helper('sslBaseExpression',name,arg,{'PapyrusUtil':SimpleNamespace(ClampInt=clamp)})
        for size in [0,1,30,31,32,40]:
            values=StrictArray([0.5 if name=='ToIntArray' else 50]*size)
            result=call(values)
            assert len(result)==32
            for i in range(32):
                expected=(0 if i>=size else (int(values[i]) if name=='ToIntArray' and i==30 else
                    values[i] if i==30 else 50 if name=='ToIntArray' else 0.5))
                assert result[i]==expected, (name,size,i,result[i],expected)
    values=StrictArray([0.25]*32);values[30]=7
    get=helper('sslBaseExpression','GetIndex','Phase, Gender, Mode, id',{
        'Registry':'expr','GetNthValues':lambda *a:values})
    assert get(1,0,30,0)==7 and get(1,0,30,1)==25
    assert get(1,0,16,0)==25 and get(1,0,32,0)==0 and get(1,0,0,-1)==0
    applied=[]
    phase=helper('sslBaseExpression','ApplyPhase','ActorRef, Phase, Gender',{
        'PhaseCounts':StrictArray([2,3]),'Registry':'expr','GetNthValues':lambda *a:values,
        'ApplyPresetFloats':lambda *a:applied.append(a)})
    for invalid in [(0,0),(1,-1),(1,2),(3,0)]:
        phase('actor',*invalid);assert not applied
    phase('actor',2,0);assert len(applied)==1
    mood=[]
    smooth=helper('sslExpressionUtil','SmoothSetExpression','act, aiMood, aiStrength, aiModifier',{
        'PapyrusUtil':SimpleNamespace(ClampInt=clamp),
        'MfgConsoleFuncExt':SimpleNamespace(SetExpression=lambda *a:mood.append(a))})
    smooth('actor',7,80,0.25);assert mood==[('actor',7,20)]


def legacy_properties_and_relationships():
    import re
    from unittest.mock import patch
    from full_sixth_scripts import source
    text=source('sslThreadModel')
    for prop,env,expected in [('Victims',{'GetAllVictims':lambda:Array(['victim'])},['victim']),
                              ('BedStatus',{'_furniStatus':2,'BedTypeID':3},[1,3])]:
        block=re.search(r'\bproperty\s+'+prop+r'\b.*?endproperty',text,re.I|re.S).group()
        block=re.sub(r'function\s+get\(', 'function PropertyGet(',block,flags=re.I)
        with patch('full_sixth_scripts.source',return_value=block):
            assert helper('sslThreadModel','PropertyGet','',env)()==expected
    actor=SimpleNamespace(GetRelationshipRank=lambda other:other)
    for name,initial,expected in [('GetHighestPresentRelationshipRank',-4,3),('GetLowestPresentRelationshipRank',4,-2)]:
        positions=StrictArray()
        call=helper('sslThreadModel',name,'ActorRef',{'_Positions':positions})
        assert call(actor)==0 and call(None)==0
        positions.append(actor);assert call(actor)==0
        positions.clear();positions.extend([-2,3]);assert call(actor)==expected
    tags=[]
    clear=helper('sslActorLibrary','ClearForcedSex','akActor',{
        'SexLabRegistry':SimpleNamespace(GetSex=lambda *a:a[0]), 'TreatAsSex':lambda actor,sex:tags.append(sex)})
    for sex in range(5): clear(sex)
    assert tags==[0,1,2,0,1]


def framework_forwarding():
    for name,args in [('SelectVoice','akActor'),('SelectVoiceByTags','akActor, asTags'),
                      ('SelectVoiceByTagsA','akActor, asTags')]:
        call=helper('SexLabFramework',name,args,{'sslVoiceSlots':SimpleNamespace(**{name:lambda *a:'voice'})})
        assert call(*(['actor'] if name=='SelectVoice' else ['actor','tags']))=='voice'
    ended=[]
    thread=SimpleNamespace(AddActors=lambda *a:False,EndAnimation=lambda quick:ended.append(quick))
    call=helper('SexLabFramework','StartSex','Positions, Anims, Victim, CenterOn, AllowBed, Hook',{
        'NewThread':lambda:thread,'Log':lambda *a:None})
    assert call(Array(['actor']),Array(),None,None,True,'')==-1
    assert ended==[True]


def config_expression_controls():
    import re
    from unittest.mock import patch
    from full_sixth_scripts import source
    # Papyrus names are case-insensitive; canonicalize only the mixed-case phase field.
    text=re.sub(r'\b_phaseidx\b','_phaseIdx',source('sslConfigMenu'),flags=re.I)
    sliders=[]
    names=StrictArray(['expr'])
    levels=[2]
    def values(*args):
        return StrictArray([j/100 for j in range(30)]+[7,0.5])
    noop=lambda *a,**k:None
    env={'_expression':names,'_expressionIdx':0,'_phaseIdx':1,'_editFemale':False,
        '_high':StrictArray([9]*32),'_maxphases':StrictArray([2,2]),
        '_expressionScales':StrictArray(['linear']),'_moods':StrictArray(list(range(17))),
        '_soundmethod':StrictArray(['sync','async']),'Config':SimpleNamespace(LipsSoundTime=0),
        'TOP_TO_BOTTOM':0,'OPTION_FLAG_NONE':0,'OPTION_FLAG_DISABLED':1,
        'Utility':SimpleNamespace(CreateFloatArray=lambda n:StrictArray([0.]*n)),
        'sslBaseExpression':SimpleNamespace(GetVersion=lambda *a:0,GetLevelCounts=lambda *a:StrictArray(levels*2),
            GetNthValues=values,GetExpressionScaleMode=lambda *a:0,GetExpressionTags=lambda *a:Array(),GetEnabled=lambda *a:True),
        'DoDisable':lambda flag:int(flag)}
    for method in ['SetCursorFillMode','SetCursorPosition','AddHeaderOption','AddMenuOptionST','AddToggleOptionST',
                   'AddTextOptionST','AddStateOptionBool','AddEmptyOption']:
        env[method]=noop
    env['AddSliderOptionST']=lambda state,title,value,*rest:sliders.append((state,title,value,rest[-1]))
    with patch('full_sixth_scripts.source',return_value=text):
        call=helper('sslConfigMenu','ExpressionEditor','',env,state_names=('_expressionIdx','_phaseIdx','_low','_high','_maxphases'))
    call()
    assert call.__globals__['_high']==[]
    for state,title,value,flag in sliders:
        index,half=map(int,state.split('_')[1:])
        if 'Modifier_' in title: assert index==16+int(title.split('_')[-1])
        elif 'Phoneme_' in title: assert index==int(title.split('_')[-1])
        assert value==(values()[index] if half==0 else 0)
        assert flag==(0 if half==0 else 1)
    names.clear();sliders.clear();call();assert not sliders


def config_key_prefixes():
    import itertools
    states=[]
    call=helper('sslConfigMenu','AddStateOptionKey',
        'asOption, asOptionText, abMandatory, abSkipConflictResolution, needsRegister, abDisable',{
            'sslSystemConfig':SimpleNamespace(GetSettingInt=lambda *a:1), 'DoDisable':lambda x:0,
            'AddKeyMapOptionST':lambda state,*a:states.append(state)})
    for mandatory,skip,register in itertools.product([False,True],repeat=3):
        call('iKey','key',mandatory,skip,register,False)
        expected=('_'.join(tag for yes,tag in [(mandatory,'M'),(skip,'S'),(register,'R')] if yes)+'_').lstrip('_')+'iKey'
        assert states[-1]==expected


def pregnancy_candidates():
    positions = Array(['male0', 'female', 'male2', 'futa', 'creature'])
    aliases = Aliases(SimpleNamespace(actor=actor, GetSex=lambda sex=sex: sex,
                                    IsOrgasmAllowed=lambda: True)
                      for actor, sex in zip(positions, [0, 1, 0, 2, 3]))
    climax = Array([2])
    registry = SimpleNamespace(GetClimaxStages=lambda scene: Array(['climax']),
                               IsStageTag=lambda *args: True,
                               GetClimaxingActors=lambda *args: climax)
    call = helper('sslThreadModel', 'CanBeImpregnated',
                  'akActor, abAllowFutaImpregnation, abFutaCanPregnate, abCreatureCanPregnate', {
                      'ActorAlias': aliases, '_Positions': positions,
                      'SexLabRegistry': registry, 'GetActiveScene': lambda: 'scene',
                      '_StageHistory': Array(['climax']),
                      'PapyrusUtil': SimpleNamespace(RemoveActor=lambda values, actor: Array(v for v in values if v != actor)),
                  })
    assert call('female', False, False, False) == ['male2']
    climax.clear()
    climax.extend([3, 4])
    assert call('female', False, False, False) == []
    assert call('female', False, True, False) == ['futa']
    assert call('female', False, True, True) == ['futa', 'creature']
    climax.clear()
    climax.extend([0, 2, 2])
    assert call('female', False, False, False) == ['male0', 'male2']
    assert call('missing', False, False, False) == []
    assert call('male0', False, False, False) == []


def alias_permutation_refresh():
    class Alias:
        def __init__(self,actor): self.actor=actor;self.calls=[]
        def GetReference(self): return self.actor
        def TryLockAndUnpause(self): self.calls.append('unlock')
        def ResetPosition(self,strip,gender): self.calls.append((strip,gender))
    current=Array(['B','A']); aliases=Array([Alias('A'),Alias('B'),Alias(None)])
    # Papyrus object casts retain the underlying Actor reference.
    from full_sixth_scripts import source as read
    import full_sixth_scripts as translation
    original=translation.source
    translation.source=lambda name:re.sub(r'\s+as\s+Actor\b','',read(name),flags=re.I)
    try:
        sort=helper('sslThreadModel','SortAliasesToPositions','',{'_Positions':Array(['A','B']),
            'ActorAlias':aliases,'GetPositions':lambda:current},state_names=('_Positions',))
    finally: translation.source=original
    sort()
    assert [x.actor for x in aliases]==['B','A',None]
    env={'_Positions':Array(['A','B']),'ActorAlias':aliases,'GetPositions':lambda:current,
        'GetActiveScene':lambda:'scene','GetActiveStage':lambda:'stage',
        'SexLabRegistry':SimpleNamespace(GetStripDataA=lambda *a:Array([10,20]),GetPositionSexA=lambda *a:Array([1,2]))}
    refresh=helper('sslThreadModel','RefreshAliasesToPositions','abForce',env,state_names=('_Positions',))
    def resync(): refresh.__globals__['_Positions']=Array(current)
    refresh.__globals__['SortAliasesToPositions']=resync
    refresh(False)
    assert aliases[0].calls==['unlock',(10,1)] and aliases[1].calls==['unlock',(20,2)]
    refresh(False);assert len(aliases[0].calls)==2
    refresh(True);assert len(aliases[0].calls)==4


def similar_stage_contract():
    class IdentityArray(Array):
        def __eq__(self,other): return self is other
    all_stages=Array(['one','two','three'])
    find=helper('sslThreadModel','FindSimilarSceneStage','',{
        'Utility':SimpleNamespace(CreateStringArray=lambda n,v: Array([v]*n)),
        'GetActiveScene':lambda:'current','GetActiveStage':lambda:'active',
        'GetPlayingScenes':lambda:Array(['current','candidate']),
        'SexLabRegistry':SimpleNamespace(GetAllStages=lambda scene:all_stages),
        'CheckSpecificStageTags':lambda *a:IdentityArray([True]+[False]*12)})
    assert find()==['candidate','three']
    find.__globals__['CheckSpecificStageTags']=lambda scene,stage:IdentityArray([scene=='current']+[False]*12)
    assert find()==['','']
    calls=[];target=Array(['candidate','three'])
    timer=helper('sslThreadModel','AdvanceFromTimer','',{
        'ThreadWaitsForOrgasm':lambda:True,'FindSimilarSceneStage':lambda:target,
        'ResetScene':lambda scene:calls.append(('reset',scene)) or True,
        'GetActiveScene':lambda:'candidate','SkipTo':lambda stage:calls.append(('skip',stage)),
        'ReStartTimer':lambda:calls.append('restart'),'Log':lambda *a:None,
        'SexlabRegistry':SimpleNamespace(GetSceneName=lambda scene:scene)})
    timer();assert calls==[('reset','candidate'),('skip','three')]
    calls.clear();target.clear();target.extend(['','']);timer();assert calls==['restart']


def actor_sex_overrides():
    registry=SimpleNamespace(GetSex=lambda actor,ignore:actor[0] if ignore else actor[1])
    get=helper('sslActorLibrary','GetTrans','ActorRef',{'SexLabRegistry':registry})
    for vanilla,forced,expected in [(0,0,-1),(1,1,-1),(0,1,1),(1,0,0),(0,2,1),(2,2,1),(3,4,3)]:
        assert get((vanilla,forced))==expected
    assert get(None)==-1
    count=helper('sslActorLibrary','CountSexAll','akPositions',{'SexLabRegistry':registry})
    assert count(Array([None,(0,0),(1,1),(2,2),(3,3),(4,4),(9,9)]))==[1,1,1,1,1]


def legacy_slot_pages():
    clamp=lambda v,lo,hi:min(max(v,lo),hi)
    slots=Array([SimpleNamespace(Registered=True,Name='A'),None,SimpleNamespace(Registered=False,Name='empty'),
                 SimpleNamespace(Registered=True,Name='B'),SimpleNamespace(Registered=True,Name='C')])
    env={'Slotted':3,'Registry':Array(['A','B','C']),'GetAliases':lambda:slots,'SyncBackend':lambda:None,
        'PapyrusUtil':SimpleNamespace(ClampInt=clamp,CountBool=lambda a,v:a.count(v)),
        'Math':SimpleNamespace(Ceiling=math.ceil),
        'sslUtility':SimpleNamespace(VoiceArray=lambda n:StrictArray([None]*n),ExpressionArray=lambda n:StrictArray([None]*n)),
        'Utility':SimpleNamespace(RandomInt=lambda lo,hi:hi)}
    for script in ('sslVoiceSlots','sslExpressionSlots'):
        page_count=helper(script,'PageCount','perpage',env)
        for total in (0,1,2,3,4,128):
            page_count.__globals__['Slotted']=total
            for size in (-1,0,1,2,125,128,500):
                assert page_count(size)==math.ceil(total/clamp(size,1,128))
        page_count.__globals__['Slotted']=3
        get=helper(script,'GetSlots','page, perpage',dict(env,PageCount=page_count))
        assert [v.Name for v in get(1,2)]==['A','B']
        assert [v.Name for v in get(2,2)]==['C']
        assert get(0,2)==[] and get(3,2)==[]
    filtered=helper('sslVoiceSlots','GetList','Valid',env)
    flags=StrictArray([False,True,True]);assert [v.Name for v in filtered(flags)]==['B','C'];assert flags==[False,True,True]
    slots.clear();slots.extend(SimpleNamespace(Registered=True,Name=str(i)) for i in range(128))
    flags=StrictArray([True]*128);ret=filtered(flags)
    assert len(ret)==100 and len({x.Name for x in ret})==100 and all(flags)
    # Backend shrink must release obsolete alias IDs, including gaps.
    class Slot:
        GOTTA_LOVE_PEOPLE_WHO_THINK_REGISTRATION_FUNCTIONS_ARE_JUST_DECORATION='marker'
        def __init__(self,id):self.Registry=id
    aliases=Array([Slot('A'),None,Slot('B')])
    for script in ('sslVoiceSlots','sslExpressionSlots'):
        sync=helper(script,'SyncBackend','',{'GetAliases':lambda:aliases,
          'GetAllVoices':lambda *a:Array(['A']),'GetAllProfileIDs':lambda:Array(['A'])})
        sync();assert aliases[0].Registry=='A' and aliases[2].Registry==''


def overlay_last_layer():
    actor=SimpleNamespace(GetLeveledActorBase=lambda:SimpleNamespace(GetSex=lambda:1),
        GetBaseObject=lambda:SimpleNamespace(GetName=lambda:'actor'))
    strings={};ints={};calls=[];max_layers=[1]
    def setint(actor,key,value): ints[key]=value;calls.append(('int',key,value));return value
    env={'StorageUtil':SimpleNamespace(GetStringValue=lambda actor,key,default:strings.get(key,default),
        SetStringValue=lambda actor,key,val:strings.update({key:val}),GetIntValue=lambda actor,key,default:ints.get(key,default),
        SetIntValue=setint,SetFloatValue=lambda *a:None,IntListAdd=lambda *a:None),
        'ACTIVE_SET_PREFIX':'set','ACTIVE_LAYER_PREFIX':'layer','LAST_APPLIED_TEXTURE_PREFIX':'texture','LAST_APPLIED_TIME_PREFIX':'time',
        'APPLIED_TEXTURE_LIST':'applied','PickRandomFxSet':lambda kind:'profile','GetFxSetCount':lambda *a:max_layers[0],
        'TypeToString':lambda kind:'Oral','GetAreas':lambda:Array(),'Log':lambda *a:None,
        'SexLabUtil':SimpleNamespace(GetCurrentGameRealTime=lambda:1)}
    import full_sixth_scripts as translation
    original=translation.source
    translation.source=lambda name:original(name).replace('akTarget.GetLeveledActorBase().GetSex() as Bool', 'bool(akTarget.GetLeveledActorBase().GetSex())')
    try: overlay=helper('sslActorLibrary','BeginOverlay','akTarget, aiType',env)
    finally:translation.source=original
    for maximum in (0,1,3):
        max_layers[0]=maximum;strings.clear();ints.clear();calls.clear()
        for unused in range(maximum+2): overlay(actor,0)
        assert [call[2]for call in calls]==list(range(1,maximum+1))
        if maximum:assert strings['texture0'].endswith('/'+str(maximum)+'.dds')
        else:assert 'texture0'not in strings


def bounded_camera_wait():
    calls=[];camera=[0]
    force=helper('SexLabUtil','ForceThirdPerson','',{'GetConfig':lambda:SimpleNamespace(HasVRIK=False),
        'Game':SimpleNamespace(GetCameraState=lambda:camera[0],ForceThirdPerson=lambda:calls.append('force')),
        'Utility':SimpleNamespace(Wait=lambda delay:calls.append(delay))})
    force();assert calls.count('force')==50 and calls.count(.02)==50
    calls.clear();camera[0]=8;force();assert calls==[]
    # Player movement uses this same bounded/yielding helper.
    from full_sixth_scripts import body
    movement=body('SexLabUtil','SetActorMovement')
    assert 'ForceThirdPerson()'in movement and 'While ('not in movement


def legacy_default_positions():
    class Definition:
        def __init__(self):self.positions=[]
        def AddPosition(self,*args): self.positions.append([]);return len(self.positions)-1
        def AddCreaturePosition(self,*args):return self.AddPosition(*args)
        def AddPositionStage(self,position,event,*args,**kwargs):self.positions[position].append(event)
        def SetTags(self,*args):pass
        def Save(self,*args):pass
    for name in ('DraugrGangbang5P','FalmerGangbang5P'):
        definition=Definition()
        build=helper('sslCreatureAnimationDefaults',name,'id',{'Create':lambda id:definition,
            'SexMix':0,'Female':1,'VaginalOralAnal':7,'CreatureMale':3})
        build(0);assert [len(p)for p in definition.positions]==[4]*5
    from full_sixth_scripts import source
    hook=source('sslThreadHook')
    initialization=re.search(r'event OnInit\(\)(.*?)endEvent',hook,flags=re.I|re.S).group(1)
    assert initialization.index('Parent.OnInit()')<initialization.index('OnPlayerLoadGame()')


def matchmaker_and_install_wait():
    spells=Array(['first',None,'second']);owned={'first'};changes=[]
    def add(spell,verbose):owned.add(spell);changes.append(('add',spell))
    def remove(spell):owned.remove(spell);changes.append(('remove',spell))
    actor=SimpleNamespace(HasSpell=lambda spell:spell in owned,AddSpell=add,RemoveSpell=remove)
    desired=[True]
    synchronize=helper('sslSystemConfig','AddRemoveMatchmakerSpells','',{'GetSettingBool':lambda *a:desired[0],
        'Game':SimpleNamespace(GetPlayer=lambda:actor),'MatchMakerSpells':spells})
    synchronize();assert changes==[('add','second')]
    changes.clear();desired[0]=False;synchronize();assert changes==[('remove','first'),('remove','second')]
    spells.clear();synchronize()
    for supported,complete_after in ((False,None),(True,None),(True,3),(True,0)):
        system=SimpleNamespace(IsInstalled=complete_after==0);waits=[];refresh=[]
        def wait(delay):
            waits.append(delay)
            if complete_after and len(waits)>=complete_after:system.IsInstalled=True
        install=helper('sslConfigMenu','InstallMenu','',{'SetCursorFillMode':lambda *a:None,'TOP_TO_BOTTOM':0,
            'AddHeaderOption':lambda *a:None,'GetStringVer':lambda:'version','SystemCheckOptions':lambda:None,
            'SetCursorPosition':lambda *a:None,'AddTextOption':lambda *a:None,'SystemAlias':system,
            'Config':SimpleNamespace(CheckSystem=lambda:supported),'Utility':SimpleNamespace(WaitMenuMode=wait),
            'ForcePageReset':lambda:refresh.append(True)})
        install();assert len(waits)==(0 if not supported else 120 if complete_after is None else complete_after)
        assert bool(refresh)==(supported and complete_after is not None)


def legacy_diagnostic_boundaries():
    benchmark=helper('sslBenchmark','StartBenchmark','Tests, Iterations, Loops, UseBaseLoop',{
        'Setup':lambda:(_ for _ in ()).throw(AssertionError('invalid benchmark must not start'))})
    for args in [(0,1,1),(-1,1,1),(129,1,1),(1,-1,1),(1,1,0),(1,1,-1)]: benchmark(*args,False)
    # Every state implementation must terminate for a negative direct RunTest request.
    import full_sixth_scripts as translation
    original=translation.source;text=original('sslBenchmark')
    variants=re.findall(r'float function RunTest[^\n]*\n.*?endFunction',text,flags=re.I|re.S)
    for variant in variants:
        translation.source=lambda name:variant
        try:
            run=helper('sslBenchmark','RunTest','nth, baseline',{'Utility':SimpleNamespace(GetCurrentRealTime=lambda:0)})
            assert run(-1,0)==0 and run(0,0)==0
        finally:translation.source=original
    trouble=original('sslTroubleshoot')
    assert 'Animations = AnimSlots.GetSlots(1, 128)'in trouble
    assert 'int i = Animations.Length'in trouble
    assert 'while i < sslThreadSlots.GetTotalThreadCount()'in trouble


if __name__ == '__main__':
    failures = []
    for test in (pregnancy_candidates, stage_history, stage_timers, rejected_scene_reset, tag_filters,
                 alias_boundaries, offset_arrays, canceled_move, registry_sex_flags, base_object_tags, bed_helpers, expression_selection, expression_sparse_filter, expression_registration, voice_registration, legacy_animation_data, stripping_weapons, creature_filters, gender_sorting, expression_units, legacy_properties_and_relationships, framework_forwarding, config_expression_controls, config_key_prefixes, alias_permutation_refresh, similar_stage_contract, actor_sex_overrides, legacy_slot_pages, overlay_last_layer, bounded_camera_wait, legacy_default_positions, matchmaker_and_install_wait, legacy_diagnostic_boundaries):
        try:
            test()
            print(f'PASS: {test.__name__} (translated Papyrus, not VM)')
        except Exception as error:
            failures.append(test.__name__)
            print(f'FAIL: {test.__name__}: {type(error).__name__}: {error}')
    if failures:
        raise SystemExit(', '.join(failures))
