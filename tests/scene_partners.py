"""Extract the real native finder; supply only engine/library data stand-ins."""
from source_regressions import ROOT, function, run
source = (ROOT / 'src/Papyrus/sslLibrary/sslThreadLibrary.cpp').read_text()
code = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <memory>
#include <string>
#include <vector>
#include "Util/RequiredMatching.h"
namespace std::ranges { template<class C, class V> bool contains(const C& c, const V& v) {return std::find(c.begin(),c.end(),v)!=c.end();} }
struct VM {int errors{};void TraceStack(const char*,int){++errors;}};
using StackID=int;
enum class LegacySex { None=-1, Male=0, Female=1, CrtMale=2, CrtFemale=3 };
namespace Settings {bool bCreatureGender=false;}
namespace std {template<class E>int to_underlying(E e){return static_cast<int>(e);}
 template<class...T>string format(const char* message,T...){return message;} }
namespace RE {
struct Point {float x{};float z{};float GetDistance(const Point& p) const {return std::sqrt(GetSquaredDistance(p));} float GetSquaredDistance(const Point& p) const {return (x-p.x)*(x-p.x);} };
struct TESObjectREFR {Point position;Point GetPosition() const {return position;}float GetPositionZ()const{return position.z;} };
struct Actor:TESObjectREFR {int race{};bool valid=true;};
struct StaticFunctionTag{};using VMStackID=int;
enum class ForEachResult {kContinue};namespace BSContainer {using ForEachResult=RE::ForEachResult;}
struct TESQuest{};using BSFixedString=std::string;
struct Handle {std::shared_ptr<Actor> actor;std::shared_ptr<Actor> get() const {return actor;} };
struct ProcessLists {std::vector<Handle> highActorHandles;static ProcessLists* GetSingleton(){static ProcessLists p;return &p;} };
}
LegacySex GetLegacySex(RE::Actor* a){return a->race==0?LegacySex::Male:LegacySex::CrtMale;}
namespace Registry {
struct RaceKey {enum Value {Human}; bool human;RaceKey(const std::string& s):human(s=="Human"){}
 bool Is(Value)const{return human;}bool IsCompatibleWith(RE::Actor* a)const{return (a->race==0)==human;} };
int actorChecks=0;bool IsValidActor(RE::Actor* a){++actorChecks;return a&&a->valid;}
struct Position {int race;bool CanFillPosition(RE::Actor* a) const {return a->race==race;} };
struct Scene {std::vector<Position> positions;};
struct Library {Scene scene;static Library* GetSingleton(){static Library l;return &l;}const Scene* GetSceneById(const std::string& s){return s=="scene"?&scene:nullptr;} };
}
'''
code += r'''
namespace Registry {struct FurnitureType {static bool IsBedType(RE::TESObjectREFR*){return true;} };}
namespace Util {int searches{};template<class F>void ForEachObjectInRange(RE::TESObjectREFR* c,float,F f){++searches;f(c);} }
'''
code += function(source, 'std::vector<RE::TESObjectREFR*> FindBeds(')
code += function(source, 'std::vector<RE::Actor*> FindAvailableActors(')
code += function(source, 'std::vector<RE::Actor*> FindAnimationPartnersImpl(')
code += r'''
int main() {
 VM vm;RE::TESObjectREFR center;
 for(float radius:{-1.f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
  assert(FindBeds(&vm,0,nullptr,&center,radius,0).empty());assert(Util::searches==0);
 }
 assert(FindBeds(&vm,0,nullptr,&center,100,std::numeric_limits<float>::quiet_NaN()).empty());assert(Util::searches==0);
 assert(FindBeds(&vm,0,nullptr,&center,100,0).size()==1);
 assert(FindBeds(&vm,0,nullptr,&center,100,-1).size()==1);
 auto human=std::make_shared<RE::Actor>();human->race=0;
 auto creature=std::make_shared<RE::Actor>();creature->race=1;
 RE::ProcessLists::GetSingleton()->highActorHandles={{human},{creature}};
 Registry::Library::GetSingleton()->scene.positions={{0},{1}};
 for(float radius:{-1.f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()})
  assert(FindAvailableActors(&vm,0,nullptr,&center,radius,LegacySex::None,nullptr,nullptr,nullptr,nullptr,"").empty());
 assert(FindAvailableActors(&vm,0,nullptr,&center,100,LegacySex::None,nullptr,nullptr,nullptr,nullptr,"").size()==1);
 assert(FindAvailableActors(&vm,0,nullptr,&center,100,LegacySex::None,nullptr,nullptr,nullptr,nullptr,"Creature").size()==1);
 auto result=FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,{});
 assert((result==std::vector<RE::Actor*>{human.get(),creature.get()}));
 result=FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,{creature.get()});
 assert((result==std::vector<RE::Actor*>{human.get(),creature.get()}));
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,{human.get(),human.get()}).empty());
 creature->valid=false;
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,{}).empty());creature->valid=true;
 creature->position.x=101;Registry::actorChecks=0;
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,100,{}).empty());assert(Registry::actorChecks==1);creature->position.x=0;
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",nullptr,100,{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,-1,{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,std::numeric_limits<float>::quiet_NaN(),{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"scene",&center,std::numeric_limits<float>::infinity(),{}).empty());
}
'''
run('scene_partners', code)
print('PASS: mixed species candidates, required actors, validity, distance and invalid search inputs')
