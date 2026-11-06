"""Execute extracted PSC bodies using small Python engine stand-ins.

This tests deterministic algorithm/state branches, not Papyrus VM scheduling or
Skyrim integration. --baseline-ref HEAD demonstrates the old failures. The
limited translator preserves branches, loops and return expressions; strict
array access exposes accesses that Papyrus would log and replace with defaults.
"""
from pathlib import Path
from types import SimpleNamespace as NS
import argparse
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()


class Array(list):
    @property
    def Length(self): return len(self)
    length = Length

    def Find(self, value, start=0):
        try: return self.index(value, start)
        except ValueError: return -1

    def __getitem__(self, key):
        if isinstance(key, int) and (key < 0 or key >= len(self)):
            raise IndexError(key)
        return super().__getitem__(key)


class Returned(Exception):
    def __init__(self, value=None): self.value = value


def source(name):
    path = f'dist/Source/Scripts/{name}.psc'
    if args.baseline_ref:
        return subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{path}'], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8')


def body(name, func, occurrence=0):
    pattern = r'(?ims)^\s*(?:\w+(?:\[\])?\s+)?function\s+' + re.escape(func) + r'\([^\n]*\)[^\n]*\n(.*?)^\s*endfunction'
    return re.findall(pattern, source(name))[occurrence]


TYPES = r'(?:bool|int|float|string|Actor|Form|Sound|ObjectReference|Alias|ssl\w+)'


def numeric_casts(line):
    while match := re.search(r'(?i)\s+as\s+int\b', line):
        end = match.start()
        start = end - 1
        if line[start] == ')':
            depth = 1
            start -= 1
            while depth:
                depth += (line[start] == ')') - (line[start] == '(')
                if depth: start -= 1
        else:
            while start > 0 and (line[start - 1].isalnum() or line[start - 1] == '_'): start -= 1
        line = line[:start] + 'int(' + line[start:end] + ')' + line[match.end():]
    return line


def execute(text, env):
    declarations, output, level = {}, [], 0
    for raw in text.splitlines():
        # Semicolons inside strings are retained.
        line = re.split(r';(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)', raw, maxsplit=1)[0].strip()
        if not line: continue
        low = line.lower()
        if low in ('endif', 'endwhile'):
            level -= 1
            continue
        declaration = re.match(r'(?i)^(' + TYPES + r'(?:\[\])?)\s+(\w+)(?:\s*=\s*(.*))?$', line)
        if declaration:
            typ, key, expr = declaration.groups()
            default = Array() if typ.endswith('[]') else {'int': 0, 'float': 0.0, 'bool': False, 'string': ''}.get(typ.lower())
            declarations[key] = default
            if expr is None: continue
            line = key + ' = ' + expr
        line = re.sub(r'(?i)\bnew\s+(' + TYPES + r')\[(\d+)\]', lambda m: f'Array([{ {"int":"0", "float":"0.0", "bool":"False", "string":"chr(0)"}.get(m[1].lower(), "None") }] * {m[2]})', line)
        line = re.sub(r'(?i)\s+as\s+(?:Actor|Form|ObjectReference|ssl\w+)\b', '', line)
        # Numeric casts used by the tested algorithms.
        line = numeric_casts(line)
        line = line.replace('&&', ' and ').replace('||', ' or ')
        line = re.sub(r'!(?!=)', 'not ', line)
        for word, replacement in [('true', 'True'), ('false', 'False'), ('none', 'None')]:
            line = re.sub(r'\b' + word + r'\b', replacement, line, flags=re.I)
        if re.match(r'(?i)^elseif\b', line):
            level -= 1
            line = 'elif ' + line[6:].strip() + ':'
        elif low == 'else':
            level -= 1
            line = 'else:'
        elif re.match(r'(?i)^if\b', line): line = 'if ' + line[2:].strip() + ':'
        elif re.match(r'(?i)^while\b', line): line = 'while ' + line[5:].strip() + ':'
        elif re.match(r'(?i)^return\b', line): line = 'raise Returned(' + line[6:].strip() + ')'
        output.append('    ' * level + line)
        if line.endswith(':'): level += 1
    assert level == 0
    scope = dict(env)
    scope.update(declarations)
    scope.update(Array=Array, Returned=Returned)
    try:
        exec(compile('\n'.join(output), 'extracted PSC', 'exec'), scope)
    except Returned as ret:
        return ret.value, scope
    return None, scope


utility = NS(CreateBoolArray=lambda n, value=False: Array([value] * n),
             CreateFloatArray=lambda n: Array([0.0] * n), CreateIntArray=lambda n: Array([0] * n),
             RandomInt=lambda low, high: high, Wait=lambda n: None)
papyrus = NS(ClampInt=lambda value, low, high: max(low, min(value, high)),
             ActorArray=lambda n: Array([None] * n), PushForm=lambda arr, value: Array([*arr, value]),
             CountBool=lambda arr, value: arr.count(value))
common = dict(Utility=utility, PapyrusUtil=papyrus, Log=lambda *args: None)
results = []


def test(name, fn):
    try:
        fn()
        print('PASS', name)
        results.append(True)
    except Exception as error:
        print('FAIL', name, type(error).__name__, str(error))
        results.append(False)


def slot_contention():
    clock, remaining = [0.0], []
    util = NS(GetCurrentRealTime=lambda: clock[0], WaitMenuMode=lambda delay: clock.__setitem__(0, clock[0] + delay))
    claimed = object()
    env = dict(Utility=util, TimeOut=1.0, GetState=lambda: 'Locked' if clock[0] < .2 else 'Ready',
               PickModel=lambda timeout=5: remaining.append(timeout) or claimed)
    result, _ = execute(body('sslThreadSlots', 'PickModel', 1), env)
    assert result is claimed and 0 < remaining[0] < 1
    clock[0] = 0
    calls = [0]
    def blocked():
        calls[0] += 1
        assert calls[0] < 40, 'unbounded timeout'
        return 'Locked'
    result, _ = execute(body('sslThreadSlots', 'PickModel', 1), dict(env, GetState=blocked, TimeOut=.2))
    assert result is None and clock[0] <= .31
    # Lock releases during a final sleep, but the total budget has expired.
    clock[0] = 0
    remaining.clear()
    result, _ = execute(body('sslThreadSlots', 'PickModel', 1), dict(env, TimeOut=.05, GetState=lambda: 'Locked' if clock[0] == 0 else 'Ready'))
    assert result is None and not remaining
test('P03 allocation result and total wait budget', slot_contention)


def timer_paths():
    subscribed = [True]
    control = dict(common, UnregisterForUpdate=lambda: subscribed.__setitem__(0, False),
                   RegisterForSingleUpdate=lambda delay: subscribed.__setitem__(0, True), ANIMATING_UPDATE_INTERVAL=.5)
    control.update(PlaybackRevision=1, IsCurrentPlayback=lambda revision: revision == 1,
                   ResumePlaybackUpdates=lambda revision: subscribed.__setitem__(0, revision == 1))
    env = dict(control, _sceneResetSyncPending=False, _nextSceneResetAt=0, _animationSyncPending=False,
               SexLabUtil=NS(GetCurrentGameRealTime=lambda: 1), asNewScene='bad', GetActiveScene=lambda: 'old',
               _Positions=Array(), _StageHistory=Array(['a']), AddExperience=lambda *a: None, SetActiveScene=lambda s: False)
    value, _ = execute(body('sslThreadModel', 'ResetScene'), env)
    assert value is False and subscribed[0]
    env = dict(control, SexLabRegistry=NS(IsCompatibleCenter=lambda *a: True), Game=NS(GetPlayer=lambda: 'player'),
               GetActiveScene=lambda: 'scene', _bOpenedSceneHUD=False,
               StorageUtil=NS(GetIntValue=lambda *a: 0), RepositionInfoMsg=NS(Show=lambda: 1))
    execute(body('sslThreadController', 'MoveScene'), env)
    assert subscribed[0]
    subscribed[0] = False
    center = NS()
    execute(body('sslThreadModel', 'CenterOnObject', 1), dict(control, CenterOn=center, _Positions=Array([center]),
        SetFurnitureIgnored=lambda value: None, ReassignCenter=lambda ref: False,
        Config=NS(HasThreadControl=lambda thread: False), Self=object()))
    assert subscribed[0]
    # Settling no-op owns no timer cancellation; random wrapper must not cancel it first.
    execute(body('sslThreadController', 'PickRandomScene'), dict(control, asNewScene='next',
        GetPlayingScenes=lambda: Array(['old', 'next']), GetActiveScene=lambda: 'old', SendThreadEvent=lambda event: None,
        ResetScene=lambda scene: True))
    assert subscribed[0]
test('P04 failed reset, cancelled movement and settling no-op keep polling', timer_paths)


def cancelled_dialog_sessions():
    for kind in ('move', 'center'):
        for outcome in ('same', 'ending', 'idle', 'making', 'reused', 'synchronizing'):
            state = dict(revision=7, phase='Animating', pending=False)
            registered, side_effects = [], []
            def current(revision):
                return execute(body('sslThreadModel', 'IsCurrentPlayback'), dict(
                    aiRevision=revision, PlaybackRevision=state['revision'],
                    GetState=lambda: state['phase'], STATE_PLAYING='Animating'))[0]
            def resume(revision):
                execute(body('sslThreadModel', 'ResumePlaybackUpdates'), dict(
                    aiRevision=revision, IsCurrentPlayback=current, _animationSyncPending=state['pending'],
                    RegisterForSingleUpdate=lambda delay: registered.append((state['phase'], delay)),
                    ANIMATING_UPDATE_INTERVAL=.5))
            def show():
                if outcome != 'same':
                    state['phase'] = {'ending':'Ending', 'idle':'Unlocked', 'making':'Making',
                                      'reused':'Animating', 'synchronizing':'Animating'}[outcome]
                    if outcome != 'synchronizing':
                        state['revision'] += 1
                    state['pending'] = outcome == 'synchronizing'
                return 1 if kind == 'move' else 0
            env = dict(common, PlaybackRevision=7, IsCurrentPlayback=current, ResumePlaybackUpdates=resume,
                       UnregisterForUpdate=lambda: None, ANIMATING_UPDATE_INTERVAL=.5,
                       RegisterForSingleUpdate=lambda delay: registered.append((state['phase'], delay)))
            if kind == 'move':
                env.update(SexLabRegistry=NS(IsCompatibleCenter=lambda *a: True),
                    Game=NS(GetPlayer=lambda: 'player'), GetActiveScene=lambda: 'scene',
                    _bOpenedSceneHUD=False, StorageUtil=NS(GetIntValue=lambda *a: 0),
                    RepositionInfoMsg=NS(Show=show))
                execute(body('sslThreadController', 'MoveScene'), env)
            else:
                center = object()
                env.update(CenterOn=center, _Positions=Array([center]),
                    SetFurnitureIgnored=lambda flag: side_effects.append(flag),
                    ReassignCenter=lambda ref: False, Config=NS(HasThreadControl=lambda thread: True),
                    Self=object(), InvalidCenterMsg=NS(Show=show),
                    EndAnimation=lambda: side_effects.append('end'))
                execute(body('sslThreadModel', 'CenterOnObject', 1), env)
            assert registered == ([('Animating', .5)] if outcome == 'same' else []), (kind, outcome, registered)
            assert 'end' not in side_effects
    # Entry/exit and explicit end invalidate the ticket, including reuse in Animating.
    animating = source('sslThreadModel').split('State Animating', 1)[1].split('EndState', 1)[0]
    assert re.search(r'Event OnBeginState\(\)\s+PlaybackRevision \+= 1', animating)
    assert 'PlaybackRevision += 1' in body('sslThreadModel', 'EndAnimation', 2)
    assert re.search(r'Event OnEndState\(\)\s+UnregisterForUpdate\(\)\s+PlaybackRevision \+= 1', source('sslThreadModel'))

test('P04 dialog cancellation rejects ended/reused sessions and pending synchronization', cancelled_dialog_sessions)


def timer_index():
    env = dict(common, Timers=Array([10., 15., 25., 7.]), GetActiveScene=lambda: '', GetActiveStage=lambda: '',
               SexLabRegistry=NS(GetClimaxingActors=lambda *a: Array()), Config=NS(StageTimer=Array([10., 15., 25., 7.])))
    for depth, expected in [(1, 10), (2, 15), (3, 25), (8, 25)]:
        result, _ = execute(body('sslThreadModel', 'GetStageTimer'), dict(env, _StageHistory=Array(['s'] * depth)))
        assert result == expected, (depth, result)
    result, _ = execute(body('sslThreadModel', 'GetStageTimer'), dict(env, Timers=Array([8.]), _StageHistory=Array(['s'])))
    assert result == 8
test('P05 stage timers use one-based history and safe singleton timers', timer_index)


def pathing():
    for flag, expected in [(-9, -1), (0, 0), (9, 1)]:
        _, env = execute(body('sslActorAlias', 'SetPathing'), dict(common, _PathingFlag=0, aiPathingFlag=flag, PATHING_DISABLE=-1, PATHING_FORCE=1))
        assert env['_PathingFlag'] == expected
test('P06 pathing argument', pathing)


def hands():
    right, left, metadata = object(), object(), {}
    actor = NS(GetWornForm=lambda slot: False, GetEquippedObject=lambda hand: right if hand else left,
               UnequipItemEX=lambda *a: None, EquipSlot_RightHand=1, EquipSlot_LeftHand=2)
    env = dict(common, akActor=actor, aiSlots=0, abStripWeapons=True, abAnimate=False,
               UnequipSlots=lambda *a: Array(), IsStrippable=lambda item: True,
               StorageUtil=NS(SetIntValue=lambda item, key, value: metadata.__setitem__(item, value)))
    result, _ = execute(body('sslActorLibrary', 'StripActorImpl'), env)
    assert result == [right, left] and metadata == {right: 1, left: 2}
test('P07 independent right/left weapon restore metadata', hands)


def voice_returns():
    slots = NS(SelectVoice=lambda *a: 'voice', SelectVoiceByTags=lambda *a: 'tagvoice', SelectVoiceByTagsA=lambda *a: 'arrayvoice')
    for fn, expected in [('SelectVoice','voice'), ('SelectVoiceByTags','tagvoice'), ('SelectVoiceByTagsA','arrayvoice')]:
        value, _ = execute(body('SexLabFramework', fn), dict(sslVoiceSlots=slots, akActor=1, asTags='tag'))
        assert value == expected
test('P10 voice ID return values', voice_returns)


def stages():
    path = Array(['first','second','last'])
    env = dict(common, Registry='scene', SexLabRegistry=NS(GetPathMax=lambda *a: path))
    stage_env = dict(env)
    def bounded(depth): return execute(body('sslBaseAnimation','GetStageBounded'),dict(stage_env,aiDepth=depth))[0]
    assert [bounded(i) for i in (0,1,2,3,9)] == ['first','first','second','last','last']
    native = NS(GetAnimationEventA=lambda scene, stage: Array([stage]), GetAnimationEvent=lambda scene, stage, pos: stage)
    env.update(GetStageBounded=bounded, GetMaxDepth=lambda: len(path), Stage=2, Position=0,
               SexLabRegistry=native, SexlabRegistry=native)
    assert execute(body('sslBaseAnimation','FetchStage'),env)[0] == ['second']
    assert execute(body('sslBaseAnimation','FetchPositionStage'),env)[0] == 'second'
    events = Array([None] * 5)
    execute(body('sslBaseAnimation','GetAnimEvents'),dict(env, AnimEvents=events))
    assert events[0] == 'second'
    updated=[]
    execute(body('sslBaseAnimation','UpdateAdjustmentAll'),dict(GetMaxDepth=lambda:3,AdjustKey='',Position=0,Slot=0,AdjustBy=1,
        UpdateAdjustment=lambda key,pos,stage,slot,delta:updated.append(bounded(stage))))
    assert updated == list(path)
    path.clear()
    assert bounded(0) == ''
test('P11/P13 legacy stage0/1 alias, stage IDs and all-stage loop', stages)


def offsets():
    native=NS(GetPathMax=lambda *a:Array(['a','b']), GetActorCount=lambda *a:2,
        GetStageOffset=lambda scene,stage,pos:Array([(0 if stage=='a' else 8)+pos*4+j for j in range(4)]))
    result,_=execute(body('sslBaseAnimation','GetAllAdjustments'),dict(common,Registry='scene',SexLabRegistry=native))
    assert result==list(range(16))
test('P12 flattened stage/actor offset stride',offsets)


def merging():
    for first,second,expected in [(['a'],['b'],['a','b']), (['a'],['a','b','b'],['a','b']), ([],['b'],['b']),
        (list(range(127)),[127,128],list(range(128))), (list(range(128)),[128],list(range(128)))]:
        original=list(first)
        env=dict(common,List1=Array(first),List2=Array(second),AnimationArray=lambda n:Array([None]*n),
            sslUtility=NS(IncreaseAnimation=lambda by,arr:Array([*arr,*([None]*by)])))
        result,_=execute(body('sslUtility','MergeAnimationLists'),env)
        assert result==expected and env['List1']==original
test('P14 merge preserves inputs/order, deduplicates and caps128',merging)


def expressions():
    aliases=Array([NS(Registered=True,id='a'),NS(Registered=False,id='unused'),NS(Registered=True,id='b'),NS(Registered=True,id='c')])
    for mask,expected in [([False,True,False],['b']),([True,False,True],['a','c'])]:
        result,_=execute(body('sslExpressionSlots','GetList'),dict(common,Valid=Array(mask),GetAliases=lambda:aliases,
            sslUtility=NS(ExpressionArray=lambda n:Array([None]*n))))
        assert [a.id for a in result]==expected
    for fn in ('PickByStatus','RandomByTag'):
        result,_=execute(body('sslExpressionSlots',fn),dict(common,ActorRef=1,IsVictim=False,IsAggressor=False,Tag='',ForFemale=True,
            GetByStatus=lambda *a:Array(['only']),GetByTag=lambda *a:Array(['only'])))
        assert result=='only'
test('P15 filter input/output cursors and inclusive RNG upper bound',expressions)


def phoneme():
    writes=[]
    env=dict(common,ActorRef=1,SoundRef=None,Strength=1.0,SoundCut=0,MoveTime=.2,Phoneme=1,MinValue=20,MaxValue=50,
        IsFixedValue=True,sslBaseExpression=NS(GetPhoneme=lambda *a:.3),
        sslExpressionUtil=NS(SmoothSetPhoneme=lambda actor,idx,value,mult=1:writes.append((idx,value*mult))))
    execute(body('sslBaseVoice','MoveLipsEx'),env)
    assert writes[-1]==(1,30)
test('P16 restore original phoneme and strength',phoneme)


def beds():
    for kind in (1,2,3):
        env=dict(BedRef=kind,GetBedType=lambda ref:ref,BedType_Single=2,BedType_Double=3)
        assert execute(body('sslThreadLibrary','IsSingleBed'),env)[0] == (kind==2)
        assert execute(body('sslThreadLibrary','IsDoubleBed'),env)[0] == (kind==3)
test('P17 legacy bed predicates (native bitmask adapter tested separately)',beds)


def statistics():
    native=NS(GetAllEncounters=lambda *a:Array(['a','b','c']),GetTimesMet=lambda player,actor:dict(a=1,b=8,c=3)[actor])
    for limit,expected in [(0,[]),(1,['b']),(3,['b','c','a']),(5,['b','c','a'])]:
        result,_=execute(body('sslActorStats','MostUsedPlayerSexPartners'),dict(common,MaxActors=limit,SexLabStatistics=native,Game=NS(GetPlayer=lambda:1)))
        assert result==expected,(limit,result)
    writes=[]
    execute(body('sslActorStats','SetFloat'),dict(ActorRef=1,Stat='TimeSpent',Value=2.5,SkillNames=lambda:Array(['TimeSpent']),
        SetLegacyStatistic=lambda actor,index,value:writes.append(value),SetStat=lambda *a:None))
    assert writes==[2.5]
test('P18 sorted limited statistics and float value',statistics)


def editor():
    text=body('sslConfigMenu','ExpressionEditor')
    # Execute the real contiguous legacy-page assignment block and real disabled-column block.
    assignments=text[text.index('\t\t_low ='):text.index('\n\tElse',text.index('\t\t_low ='))]
    env=dict(common,_expression=Array(['legacy']),_expressionIdx=0,_editFemale=False,_phaseidx=2,maxphase=3,_high=Array([9.]*32),
        sslBaseExpression=NS(GetNthValues=lambda *a:Array([1.]*32)))
    _,out=execute(assignments,env)
    assert not out['_high']
    render=re.search(r'(?ms)^\s*If \(i == 0\)\s*\n\s*values = _low.*?\n\s*EndIf\s*\n\s*AddHeaderOption',text)[0]
    render=render[:render.rfind('AddHeaderOption')]
    _,out=execute(render,dict(out,i=1,OPTION_FLAG_DISABLED=1,flag=0))
    assert out['flag']==1 and len(out['values'])==32 and out['values'][31]==0
test('P19 stale high phase cleared and disabled column indexes safe',editor)

print(f'{sum(results)}/{len(results)} regression groups passed; engine stand-ins, not a Papyrus VM test.')
raise SystemExit(0 if all(results) else 1)
