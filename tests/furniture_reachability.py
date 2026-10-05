"""Exercise the actual reachability lambda with a misbehaving cast result."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/ThreadCtor.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <stdexcept>
#include <utility>
#include <vector>
namespace std::ranges {template<class C,class V>bool contains(const C& c,const V& v){return std::find(c.begin(),c.end(),v)!=c.end();}}
struct Point{};
namespace RE {
enum class FormType {Static,MovableStatic,Furniture,Door,ActorCharacter};
struct Base {FormType type=FormType::ActorCharacter;template<class...T>bool Is(T...types){return ((type==types)||...);} };
struct TESObjectREFR;
struct NiAVObject {TESObjectREFR* ref{};TESObjectREFR* GetUserData(){return ref;} };
struct TESObjectREFR {Base base;NiAVObject obj{this};NiAVObject* Get3D(){return &obj;}Base* GetBaseObject(){return &base;}bool IsLocked(){return false;} };
}
namespace Raycast {
struct Result {bool hit;RE::NiAVObject* hitObject;Point hitPos;};
int calls=0,mode=0;RE::TESObjectREFR obstruction;
Result hkpCastRay(Point,Point,const std::vector<RE::NiAVObject*>&){
 if(++calls>100)throw std::runtime_error("unbounded ray traversal");
 if(mode==0)return {true,&obstruction.obj,{}};
 if(mode==1)return {false,nullptr,{}};
 static std::vector<RE::TESObjectREFR> chain(100);
 return {true,&chain[calls-1].obj,{}};
}
}
bool check(){
 RE::TESObjectREFR center,actor;auto* a_ref=&center;
 Point endPoint;std::vector<std::pair<RE::TESObjectREFR*,Point>> raycastStart{{&actor,{}}};
'''
code += function(source,'const auto isReachable =')+');\nreturn isReachable;\n}\n'
code += r'''
int main(){
 Raycast::calls=0;Raycast::mode=0;assert(!check());assert(Raycast::calls<=2);
 Raycast::calls=0;Raycast::mode=1;assert(check());assert(Raycast::calls==1);
 Raycast::calls=0;Raycast::mode=2;assert(!check());assert(Raycast::calls==64);
}
'''
run('furniture_reachability',code)
print('PASS: reachable path, repeated obstacle and maximum traversal work')
