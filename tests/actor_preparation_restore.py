"""Actual native prepare/restore functions with actor API stand-ins; not VM/ABI."""
from source_regressions import ROOT,function,run
import os, subprocess
def production(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
    return (ROOT/path).read_text()
source=production('src/Thread/ThreadAnimation.cpp')
code=r'''
#include <cassert>
#include <iostream>
#include <mutex>
#include <unordered_map>
#include <vector>
#include <cstdint>
namespace RE {
 using FormID=unsigned;
 enum class ACTOR_LIFE_STATE {kAlive,kRestrained,kDead,kDying,kUnconcious};
 enum class ActorValue {kParalysis,kVariable05};
 struct TESQuest {unsigned GetFormID(){return 1;}};struct TESFaction{};
 struct Actor {
  struct {ACTOR_LIFE_STATE lifeState=ACTOR_LIFE_STATE::kAlive;} actorState1;
  struct {bool forceSneak=false;} actorState2;
  bool player=false,foot=false;int npc=1;float variable=42,paralysis=1;
  bool graphPresent=true;
  FormID GetFormID(){return 1;}Actor* AsActorState(){return this;}Actor* AsActorValueOwner(){return this;}
  ACTOR_LIFE_STATE GetLifeState(){return actorState1.lifeState;}
  float GetBaseActorValue(ActorValue av){return av==ActorValue::kVariable05?variable:paralysis;}
  void SetActorValue(ActorValue av,float v){(av==ActorValue::kVariable05?variable:paralysis)=v;}
  bool GetGraphVariableInt(const char*,int& v){v=npc;return graphPresent;}
  bool GetGraphVariableBool(const char*,bool& v){v=foot;return graphPresent;}
  void SetGraphVariableInt(const char*,int v){npc=v;}void SetGraphVariableBool(const char*,bool v){foot=v;}
  void AddToFaction(TESFaction*,int){}void EvaluatePackage(){}bool IsPlayerRef(){return player;}
  void Resurrect(bool,bool){actorState1.lifeState=ACTOR_LIFE_STATE::kAlive;}
  bool IsWeaponDrawn(){return false;}void DrawWeaponMagicHands(bool){}bool IsSneaking(){return false;}
 };
}
namespace logger {template<class...T>void error(T&&...){}template<class...T>void info(T&&...){} }
namespace GameForms {inline const RE::TESFaction* AnimatingFaction=nullptr;}
namespace Hooks {void SetWeaponDrawBlocked(bool){} }
namespace Registry {struct Scale {static Scale* GetSingleton(){static Scale s;return &s;}void RemoveScale(RE::Actor*){} };}
'''
a=source.index('        enum ActorStatus');b=source.index('        bool IsPlayerDialogueActive()',a)
code+=source[a:b]
code+=function(source,'bool PrepareActorForAnimation(')+'\n'+function(source,'void RestorePreparedActorState(')
code+=r'''
int main(){
 using Life=RE::ACTOR_LIFE_STATE;RE::TESQuest owner,other;
 for(Life original:{Life::kAlive,Life::kUnconcious,Life::kDead,Life::kDying}){
  for(Life current:{Life::kRestrained,Life::kDead,Life::kDying}){
   RE::Actor actor;actor.actorState1.lifeState=original;
   assert(PrepareActorForAnimation(&owner,&actor,true));
   assert(actor.npc==0&&actor.foot&&actor.actorState1.lifeState==Life::kRestrained);
   const auto marker=actor.variable;
   assert(!PrepareActorForAnimation(&other,&actor,true));
   assert(PrepareActorForAnimation(&owner,&actor,true)&&actor.variable==marker);
   actor.actorState1.lifeState=current;
   RestorePreparedActorState(&other);assert(actor.npc==0);
   RestorePreparedActorState(&owner);
   assert(actor.variable==42&&actor.npc==1&&!actor.foot&&actorPreparations.empty());
   assert(actor.actorState1.lifeState==(current==Life::kRestrained?(original==Life::kUnconcious?Life::kUnconcious:Life::kAlive):current));
   RestorePreparedActorState(&owner);assert(actor.variable==42);
  }
 }
 RE::Actor actor;assert(PrepareActorForAnimation(&owner,&actor,false));
 actor.variable=99;RestorePreparedActorState(&owner);assert(actor.variable==99); // Native never owned the marker.
 actor.player=true;assert(PrepareActorForAnimation(&owner,&actor,true));
 actor.variable=77;actor.actorState1.lifeState=Life::kDead;RestorePreparedActorState(&owner);
 assert(actor.variable==77&&actor.actorState1.lifeState==Life::kDead);
 std::cout<<"PASS: actual native restore preserves completed/new deaths, original markers and thread ownership\n";
}
'''
run('actor_preparation_restore',code)
