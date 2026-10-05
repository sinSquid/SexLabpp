"""Actual legacy Papyrus helpers with strict arrays; no VM/runtime claim."""
from types import SimpleNamespace as NS
from full_sixth_scripts import helper, Array
class StrictArray(Array):
    def __getitem__(self,index):
        assert 0 <= index < len(self), (index,len(self))
        return super().__getitem__(index)
clamp=lambda v,lo,hi:max(lo,min(hi,v))
for counts in ([0,0],[1,3],[128,128]):
    pick=helper('sslBaseExpression','PickPhase','Strength,Gender',{'PhaseCounts':StrictArray(counts),'PapyrusUtil':NS(ClampInt=clamp)})
    for gender in (-1,0,1,2,2147483647):
        for strength in (-1,1,50,100,2147483647):
            result=pick(strength,gender)
            assert result==0 if gender not in (0,1) or counts[gender]==0 else 1<=result<=counts[gender]
for length in (0,32):
    preset=StrictArray([0.0]*length);writes=[]
    env={'Registry':'id','GetNthValues':lambda *args:preset,'SetPhase':lambda *args:writes.append(args)}
    write=helper('sslBaseExpression','SetIndex','Phase,Gender,Mode,id,value',env)
    read=helper('sslBaseExpression','GetIndex','Phase,Gender,Mode,id',env)
    for phase,gender,mode,index in ((0,0,0,0),(1,-1,0,0),(1,2,0,0),(1,0,-1,0),(1,0,31,1),(1,0,2147483647,2147483647),(1,0,0,-1)):
        write(phase,gender,mode,index,50);assert read(phase,gender,mode,index)==0
    assert not writes
    write(1,1,30,1,70)
    if length:assert preset[31]==0.7 and len(writes)==1 and read(1,1,30,1)==70
    else:assert not writes
count=helper('sslActorLibrary','GenderCount','Positions',{'GetGender':lambda actor:actor})
assert count(StrictArray([-1,0,1,2,3,4,2147483647]))==[1,1,1,1]
for length in (0,4):
    get=helper('sslBaseAnimation','GetAdjustment','AdjustKey,Position,Stage,Slot',{'Registry':'id','GetStageBounded':lambda s:s,'SexLabRegistry':NS(GetStageOffset=lambda *args:StrictArray([10.,20.,30.,40.][:length]))})
    for index in (-1,0,3,4,2147483647):
        assert get('',0,1,index)==([10.,20.,30.,40.][index] if 0<=index<length else 0.)
for depth in (-1,0,1,32,33,128,2147483647):
    empty=helper('sslBaseAnimation','GetEmptyAdjustments','Position',{'GetMaxDepth':lambda:depth,'Utility':NS(CreateFloatArray=lambda size:StrictArray([0.]*size)),'PapyrusUtil':NS(ClampInt=clamp)})
    assert len(empty(0))==clamp(depth,0,32)*4
actor=NS(GetLeveledActorBase=lambda:NS(GetRace=lambda:'race'))
find=helper('sslThreadLibrary','FindNext','Positions,Animation,offset,FindCreature',{})
positions=StrictArray([actor,None,actor]);animation=NS(HasRace=lambda race:True)
for offset in (-1,4,2147483647):assert find(positions,animation,offset,True)==-1
assert find(positions,None,3,True)==-1
assert find(positions,animation,3,True)==2
assert find(positions,animation,2,True)==0
assert find(positions,animation,0,True)==-1
print('PASS: actual legacy expression/offset/gender/search guards reject invalid inputs and preserve valid behavior')
for aliases in ([],[None],[None,NS(Genders=StrictArray([0,1,0,1]))]):
    queries=[]
    race=helper('sslCreatureAnimationSlots','RaceKeyHasAnimation','RaceKey,ActorCount,Gender',{
        'GetByRaceKey':lambda *args:(queries.append(args) or StrictArray(aliases))})
    for gender in (-2,-1,0,1,2,3,4,2147483647):
        before=len(queries);actual=race('race',2,gender)
        if gender < -1 or gender > 3:assert not actual and len(queries)==before
        else:assert actual==(bool(aliases) if gender==-1 else len(aliases)==2 and gender in (1,3))
print('PASS: actual race animation helper validates genders before querying and tolerates sparse aliases')
