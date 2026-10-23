"""Execute production equipment bookkeeping with actor/form/storage stand-ins.

No Papyrus VM or engine equip scheduling is simulated by this harness.
"""
from types import SimpleNamespace as NS
from papyrus_harness import Array, helper

class Item:
    def __init__(self, name, weapon_type=None, spell=False):
        self.name,self.weapon_type,self.spell=name,weapon_type,spell
    def GetWeaponType(self): return self.weapon_type

class Actor:
    EquipSlot_RightHand,EquipSlot_LeftHand=1,2
    def __init__(self, right=None,left=None):
        self.hands={1:right,0:left}; self.equipped=[]; self.always=[]; self.worn=set(); self.slot_item=None
    def GetEquippedObject(self, hand): return self.hands[hand]
    def GetWornForm(self, slot): return self.slot_item
    def IsEquipped(self, item):return item in self.worn or item in self.hands.values()
    def UnequipItemEX(self, item, hand, _):
        self.worn.discard(item)
        if hand==0:
            self.hands={k:None if v is item else v for k,v in self.hands.items()}
            return
        if item.weapon_type in (5,6,7,9):
            self.hands={k:None if v is item else v for k,v in self.hands.items()}
        else: self.hands[1 if hand==1 else 0]=None
    def EquipItemEx(self, item, hand, _):
        self.equipped.append((item,hand)); self.worn.add(item)
        if hand: self.hands[1 if hand==1 else 0]=item

class Storage:
    def __init__(self): self.lists={}; self.old={}
    def FormListAdd(self, owner,key,item,duplicate=True):
        assert owner is not None and item is not None
        values=self.lists.setdefault((owner,key),[])
        if duplicate or item not in values: values.append(item)
        return values.index(item)
    def FormListFind(self,owner,key,item):
        values=self.lists.get((owner,key),[])
        return values.index(item) if item in values else -1
    def FormListRemove(self,owner,key,item,allInstances=False):
        values=self.lists.get((owner,key),[]);count=values.count(item)
        self.lists[owner,key]=[v for v in values if v is not item]
        return count
    def GetIntValue(self,owner,key,default=0):return self.old.get((owner,key),default)
    def UnsetIntValue(self,owner,key):return self.old.pop((owner,key),None) is not None

storage=Storage()
cast_weapon=lambda x:x if x and x.weapon_type is not None else None
remember=helper('sslActorLibrary','RememberStripItems','ActorRef,Items,RightHand,LeftHand',{'StorageUtil':storage,'_cast_weapon':cast_weapon})
restore=helper('sslActorLibrary','RestoreStripItem','ActorRef,item',{'StorageUtil':storage})
unstrip=helper('sslActorLibrary','UnstripActor','ActorRef,Stripped,IsVictim=False',{'RestoreStripItem':restore})

def unequip_slots(actor, slots):
    for item in actor.always:
        actor.hands={k:None if v is item else v for k,v in actor.hands.items()}
    return Array(actor.always)

strip=helper('sslActorLibrary','StripActorImpl','akActor,aiSlots,abStripWeapons=True,abAnimate=False',{
    'Utility':NS(CreateFormArray=lambda n:Array([None]*n),Wait=lambda _:None),
    'UnequipSlots':unequip_slots,'IsStrippable':lambda _:True,
    'PapyrusUtil':NS(PushForm=lambda values,item:Array([*values,item])),
    'RememberStripItems':remember,
    '_cast_weapon':lambda x:x if x and x.weapon_type is not None else None,
    '_cast_spell':lambda x:x if x and x.spell else None})

sword=Item('shared sword',1);shield=Item('shield');armor=Item('armor')
a,b=Actor(right=sword),Actor(left=sword)
ra,rb=strip(a,0),strip(b,0)
storage.old[sword,'Hand']=2 # An unrelated pre-upgrade pending record.
unstrip(a,ra);assert a.equipped==[(sword,1)] and not b.equipped
assert storage.old[sword,'Hand']==2
unstrip(b,rb);assert b.equipped==[(sword,2)]
dual=Actor(sword,sword);items=strip(dual,0)
unstrip(dual,Array([sword]));assert dual.equipped==[(sword,1),(sword,2)]
unstrip(dual,items);assert dual.equipped==[(sword,1),(sword,2),(sword,0)]

greatsword=Item('greatsword',5);twohand=Actor(greatsword,greatsword)
items=strip(twohand,0);unstrip(twohand,items);assert twohand.equipped==[(greatsword,1)]
held=Actor(sword,shield);held.always=[sword,shield,armor]
items=strip(held,0,False);assert not held.hands[1] and not held.hands[0]
unstrip(held,Array([None,armor,sword,sword]));assert held.equipped==[(armor,0),(sword,1)]
unstrip(held,Array([shield]));assert held.equipped[-1]==(shield,2)

pending=Actor(right=sword);old=strip(pending,0);assert strip(pending,0)==[]
unstrip(pending,old);assert pending.equipped==[(sword,1)]
spell=Item('spell',spell=True);caster=Actor(spell,spell)
assert strip(caster,0)==[] and caster.hands[1] is spell
legacy=Actor();unstrip(legacy,Array([sword,sword]));assert legacy.equipped==[(sword,2)]
assert (sword,'Hand') not in storage.old
unstrip(legacy,Array([sword]));assert legacy.equipped==[(sword,2),(sword,0)]
invalid=Item('bad record');storage.old[invalid,'Hand']=55
unstrip(legacy,Array([invalid]));assert legacy.equipped[-1]==(invalid,0)
before=dict(storage.lists);assert strip(None,0)==[];unstrip(None,Array([sword]));assert storage.lists==before

# Simulated Form relocation: only owners and Form values are remapped, never key strings.
saved=Actor(right=sword);items=strip(saved,0)
loaded,loaded_sword=Actor(),Item('same form after load',1)
for (owner,key),values in list(storage.lists.items()):
    if owner is saved:
        storage.lists[loaded,key]=[loaded_sword if v is sword else v for v in values]
unstrip(loaded,Array([loaded_sword]));assert loaded.equipped==[(loaded_sword,1)]
print('PASS: actual actor-owned hand records, dual/two-handed, early unequip, partial/dedup/repeat restore and legacy fallback')

strip_slot=helper('sslActorLibrary','StripSlot','ActorRef,SlotMask',{
    'IsStrippable':lambda _:True,'RememberStripItems':remember})
a.slot_item=sword
item=strip_slot(a,1);unstrip(a,Array([item]));assert a.equipped[-1]==(sword,1)
# External unequip and caller-created arrays retain the legacy equip-array contract.
a.UnequipItemEX(sword,0,False)
unstrip(a,Array([sword]));assert a.equipped[-1]==(sword,0)
print('PASS: StripSlot after full restore and externally unequipped caller arrays')
