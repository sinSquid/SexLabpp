"""Source-derived public thread/hook index tests; not Papyrus VM validation."""
from types import SimpleNamespace
from full_sixth_scripts import Array, helper
class StrictArray(Array):
    def __getitem__(self, index):
        assert 0 <= index < len(self)
        return super().__getitem__(index)
    def __setitem__(self, index, value):
        assert 0 <= index < len(self)
        return super().__setitem__(index,value)
for name,arg in [('GetThread','aiThreadID'),('GetController','tid')]:
    for count in (0,3,15):
        values=StrictArray(range(count))
        get=helper('sslThreadSlots',name,arg,{'Threads':values})
        for index in (-1,0,2,14,15,2147483647):
            assert get(index)==(index if 0 <= index < count else None)
thread=lambda index:SimpleNamespace(GetThreadID=lambda:index)
get=helper('SexLabThreadHook','IsLocked','akThread',{'_m':StrictArray([False]*15)})
for value in (None,thread(-1),thread(15),thread(2147483647)):
    assert get(value) is False
set_locked=helper('SexLabThreadHook','SetLocked','akThread,abLocked',{
    '_m':StrictArray(),
    'sslThreadSlots':SimpleNamespace(GetTotalThreadCount=lambda:15),
    'Utility':SimpleNamespace(CreateBoolArray=lambda size,value:StrictArray([value]*size)),
},state_names=('_m',))
set_locked(None,True)
set_locked(thread(14),True)
assert set_locked.__globals__['_m'][14] is True
for index in (-1,15,2147483647):set_locked(thread(index),True)
assert sum(set_locked.__globals__['_m'])==1
print('PASS: actual thread/hook source control flow rejects invalid indices; hook initializes storage before writing')
