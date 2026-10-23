"""Exhaustive generic matching and the real native entry point with engine stand-ins."""
from source_regressions import ROOT, function, run

run('required_slot_matching',r'''
#include <algorithm>
#include <cassert>
#include <functional>
#include <set>
#include "Util/Assignment.h"
int main(){
 for(unsigned pattern=0;pattern<4096;++pattern){
  auto bits=pattern;std::vector<uint32_t> masks(4);
  for(auto& m:masks){m=bits&7;bits>>=3;}
  for(size_t required=0;required<=4;++required){
   std::vector<size_t> selected;
   std::function<bool(size_t)> brute=[&](size_t slot){
    if(slot==3){for(size_t i=0;i<required;++i)if(std::find(selected.begin(),selected.end(),i)==selected.end())return false;return true;}
    for(size_t i=0;i<masks.size();++i){
     if(!(masks[i]&(1u<<slot))||std::find(selected.begin(),selected.end(),i)!=selected.end())continue;
     selected.push_back(i);if(brute(slot+1))return true;selected.pop_back();
    }
    return false;
   };
   const bool exists=brute(0);
   auto found=Util::MatchRequiredSlots(3,masks,required);
   assert(exists==!found.empty());
   if(!found.empty()){
    assert(found.size()==3&&std::set<size_t>(found.begin(),found.end()).size()==3);
    for(size_t slot=0;slot<3;++slot)assert(masks[found[slot]]&(1u<<slot));
    for(size_t i=0;i<required;++i)assert(std::find(found.begin(),found.end(),i)!=found.end());
   }
  }
 }
 std::vector<uint32_t> edge(32);for(unsigned i=0;i<32;++i)edge[i]=1u<<i;
 assert(Util::MatchRequiredSlots(32,edge,32).size()==32);
 assert(Util::MatchRequiredSlots(33,edge,32).empty());
 assert(Util::MatchRequiredSlots(1,{1},2).empty());
}
''')

source=(ROOT/'src/Papyrus/sslLibrary/sslThreadLibrary.cpp').read_text()
code=r'''
#include <cassert>
#include <cmath>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>
#include "Util/Assignment.h"
using StackID=int;
struct VM {void TraceStack(const char*,int) {}};
namespace RE {
struct TESQuest{};struct TESObjectREFR{};using BSFixedString=std::string;
struct Actor {unsigned id;bool human=true,child=false,valid=true,badData=false;bool IsHumanoid(){return human;}bool IsChild(){return child;}};
}
namespace Registry {
struct ActorFragment {
 static constexpr size_t MAX_ACTOR_COUNT=5; RE::Actor* actor;
 ActorFragment(RE::Actor* a,bool):actor(a){if(a->badData)throw std::runtime_error("bad");}
};
struct Position {uint32_t accepted;bool CanFillPosition(const ActorFragment& f)const{return (accepted&(1u<<f.actor->id))!=0;}};
struct Scene {std::vector<Position> positions;bool creatures=false;bool HasCreatures()const{return creatures;}};
struct Library {
 Scene scene;
 static Library* GetSingleton(){static Library x;return &x;}
 Scene* ReadScene(const std::string& id){return id=="scene"?&scene:nullptr;}
};
bool IsValidActor(RE::Actor* actor){return actor->valid;}
}
enum class LegacySex {None};
std::vector<RE::Actor*> available;
std::vector<RE::Actor*> FindAvailableActors(VM*,StackID,RE::TESQuest*,RE::TESObjectREFR*,float,LegacySex,
 RE::Actor*,RE::Actor*,RE::Actor*,RE::Actor*,const char*){return available;}
'''+function(source,'std::vector<RE::Actor*> FindAnimationPartnersImpl(')+r'''
int main(){
 VM vm;RE::TESObjectREFR center;RE::Actor a{0},b{1},c{2};
 auto& scene=Registry::Library::GetSingleton()->scene;
 scene.positions={{3},{1}};available={&a,&b,&a};
 auto find=[&](std::vector<RE::Actor*> required){return FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,required);};
 assert((find({&a})==std::vector<RE::Actor*>{&b,&a}));
 assert((find({&a,&a})==std::vector<RE::Actor*>{&b,&a}));
 assert(find({&c}).empty());assert(find({nullptr}).empty());
 a.child=true;assert(find({&a}).empty());assert(find({}).empty());a.child=false;
 a.valid=false;assert(find({&a}).empty());a.valid=true;
 a.human=false;assert(find({&a}).empty());a.human=true;
 b.badData=true;assert(find({}).empty());b.badData=false;
 scene.creatures=true;assert(find({}).empty());scene.creatures=false;
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",nullptr,100,{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,std::numeric_limits<float>::quiet_NaN(),{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"missing",&center,100,{}).empty());
 scene.positions.clear();assert(find({}).empty());
}
'''
run('native_partner_assignment',code)
