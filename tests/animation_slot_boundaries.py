"""Actual extracted animation slot control flow with strict arrays, not VM validation."""
from types import SimpleNamespace
import math
from full_sixth_scripts import Array,helper
class StrictArray(Array):
    def __getitem__(self,index):
        assert 0 <= index < len(self)
        return super().__getitem__(index)
    def __setitem__(self,index,value):
        assert 0 <= index < len(self)
        return super().__setitem__(index,value)
clamp=lambda x,low,high:max(low,min(high,x))
for count in (0,1,3,125,126,128):
    slots=StrictArray([f'A{i}' if i%4 else None for i in range(count)])
    env={'EnsureBackEnd':lambda:None,'Slotted':count,
         'GetBySlot':lambda i:slots[i],
         'Utility':SimpleNamespace(CreateIntArray=lambda size:StrictArray([0]*size),RandomInt=lambda a,b:b),
         'sslUtility':SimpleNamespace(AnimationArray=lambda size:StrictArray([None]*size)),
         'PapyrusUtil':SimpleNamespace(ClampInt=clamp),'Math':SimpleNamespace(Ceiling=math.ceil)}
    get=helper('sslAnimationSlots','GetList','Valid',env)
    flags=StrictArray([True]*128)
    expected=[item for item in reversed(slots) if item is not None]
    assert get(flags)==expected
    page_count=helper('sslAnimationSlots','PageCount','perpage=125',env)
    for perpage in (-1,0,1,125,128,200):
        assert page_count(perpage)==math.ceil(count/clamp(perpage,1,128))
# Dense cap selection is bounded even with a deterministic RNG; result retains descending slot order.
slots=StrictArray([f'A{i}' for i in range(128)])
env.update(Slotted=128,GetBySlot=lambda i:slots[i])
get=helper('sslAnimationSlots','GetList','Valid',env)
flags=StrictArray([True]*128);actual=get(flags)
assert len(actual)==125 and None not in actual and actual==list(reversed(list(slots)[:125]))
assert sum(flags)==125
print('PASS: animation list skips sparse aliases, caps selection with bounded progress; page counts handle empty/exact/invalid sizes')

runtime=helper('sslBaseAnimation','GetTimersRunTime','StageTimers',{
    'Registry':'scene',
    'SexLabRegistry':SimpleNamespace(GetPathMax=lambda *_:Array(['a','b','c']),GetFixedLength=lambda scene,stage:{'a':1000.,'b':0.,'c':2500.}[stage])})
assert runtime(StrictArray([10.,20.,30.]))==23.5
calls=[]
set_offset=helper('sslThreadController','SetSceneOffset','afOffsetValue,asOffsetType,abIncrement=False',{
    'GetActiveScene':lambda:'scene','GetOffsetIdx':lambda value:{'R':3,'X':0}.get(value,-1),
    'SexLabRegistry':SimpleNamespace(GetSceneOffset=lambda *_:StrictArray([12.,0.,0.,math.pi/2]),SetSceneOffset=lambda *args:calls.append(args)),
    'Math':SimpleNamespace(RadiansToDegrees=math.degrees),'ResetStage':lambda:None})
set_offset(10.,'R',True);assert abs(calls[-1][1]-100.)<1e-6
set_offset(5.,'X',True);assert calls[-1][1]==17.
set_offset(5.,'invalid',True);assert len(calls)==2
print('PASS: actual legacy runtime converts milliseconds to seconds; scene rotation increments convert radians to degrees and reject invalid axis')
