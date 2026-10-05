"""Actual Papyrus HUD failure paths and ownership query with API stand-ins."""
from types import SimpleNamespace as NS
import re
import full_sixth_scripts as psc
from full_sixth_scripts import helper
for owns in (False,True):
    calls=[]
    env={'GetStatus':lambda:1,'STATUS_INSCENE':1,'ElementUI_GameHUD':False,
         'RefreshPropertiesSceneHUD':lambda mode:calls.append(('refresh',mode)),
         'InitSceneHUDImpl':lambda:calls.append('init'),'DestroySceneHUDImpl':lambda:calls.append('destroy'),
         'IsSceneHUDActiveImpl':lambda:owns,'SexLabUtil':NS(HideElementsGameHUD=lambda hide:calls.append(('hide',hide)))}
    helper('sslThreadModel','TryInitSceneHUD','',env)()
    assert ('hide',True) in calls if owns else ('hide',True) not in calls
    calls.clear();helper('sslThreadModel','TryCloseSceneHUD','',env)()
    assert calls==['destroy',('refresh','Set'),('hide',False)] if owns else calls==[]
    calls.clear()
    toggle=helper('sslThreadController','ToggleVisibilitySceneHUD','aiForceState',{
        '_bOpenedSceneHUD':False,'_bFocusedSceneHUD':False,'_bOpenedSceneGraph':False,
        'TryInitSceneHUD':lambda:calls.append('init'),'IsSceneHUDActiveImpl':lambda:owns,
    },state_names=('_bOpenedSceneHUD',))
    toggle(1);assert toggle.__globals__['_bOpenedSceneHUD']==owns
# Run the actual property setter through the same limited translator.
source=psc.source('sslThreadModel')
match=re.search(r'bool Property IsAggressive hidden(.*?)EndProperty',source,re.I|re.S)
setter=re.search(r'Function set\(bool value\)(.*?)EndFunction',match[1],re.I|re.S)[1]
original_source=psc.source
try:
    psc.source=lambda _: 'Function selected(bool value)\n'+setter+'EndFunction'
    calls=[];set_aggressive=helper('','selected','value',{'SetConsent':lambda consent:calls.append(consent)})
    set_aggressive(True);set_aggressive(False);assert calls==[False,True]
finally:psc.source=original_source
get=helper('sslThreadModel','GetNthPosition','n',{'_Positions':psc.Array(['actor'])})
for index in (-1,0,1,2147483647):assert get(index)==('actor' if index==0 else None)
print('PASS: actual HUD paths honor ownership/failure; aggression setter maps to inverse consent and position reads are bounded')
# Compile the actual added native wrapper as well; registry/quest/UI are stand-ins.
from source_regressions import ROOT,function,run
native=function((ROOT/'src/Papyrus/sslThreadModel.cpp').read_text(),'bool IsSceneHUDActiveImpl(')
run('hud_ownership_native',r'''
#include <cassert>
#include <iostream>
#define QUESTARGS int* a_qst
#define GET_INSTANCE(ret) if(!a_qst) return ret
namespace Thread::Interface {
 struct SceneHUD {
  int* owner=nullptr;
  static SceneHUD& GetSingleton(){static SceneHUD h;return h;}
  void* GetForThread(int* quest){return owner&&owner==quest?this:nullptr;}
 };
}
'''+native+r'''
int main(){
 int first=1,second=2;
 assert(!IsSceneHUDActiveImpl(nullptr)&&!IsSceneHUDActiveImpl(&first));
 Thread::Interface::SceneHUD::GetSingleton().owner=&first;
 assert(IsSceneHUDActiveImpl(&first)&&!IsSceneHUDActiveImpl(&second));
 std::cout<<"PASS: actual native HUD query rejects missing instances and other owners\n";
}
''')
