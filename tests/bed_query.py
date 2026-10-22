from statistics_roundtrip import ROOT, function, run
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <vector>
namespace RE {
 using VMStackID=int;struct StaticFunctionTag{};
 struct Point {float x{},y{},z{};float GetDistance(Point p)const{return std::sqrt((x-p.x)*(x-p.x)+(y-p.y)*(y-p.y)+(z-p.z)*(z-p.z));}};
 struct TESObjectREFR {Point point;bool bed=false;Point GetPosition()const{return point;}};
 namespace BSContainer {enum class ForEachResult{kContinue};}
}
struct VM {void TraceStack(const char*,int){}};
namespace Registry {struct FurnitureType {static bool IsBedType(RE::TESObjectREFR* r){return r->bed;}};}
namespace Util {
 std::vector<RE::TESObjectREFR*> objects;
 template<class F>void ForEachObjectInRange(RE::TESObjectREFR*,float,F f){for(auto* r:objects)f(r);}
}
'''
code+=function((ROOT/'src/Papyrus/sslLibrary/sslThreadLibrary.cpp').read_text(),'std::vector<RE::TESObjectREFR*> FindBeds(')
code+=r'''
int main(){
 VM vm;RE::TESObjectREFR center{{0,0,0}},near{{1,0,0},true},far{{10,0,0},true},high{{0,0,100},true},other{{0,0,0},false};
 Util::objects={nullptr,&far,&high,&other,&near};
 assert((FindBeds(&vm,0,nullptr,&center,100,10)==std::vector<RE::TESObjectREFR*>{&near,&far}));
 assert(FindBeds(&vm,0,nullptr,&center,100,0).size()==3);
 assert(FindBeds(&vm,0,nullptr,nullptr,100,10).empty());
 assert(FindBeds(&vm,0,nullptr,&center,std::numeric_limits<float>::quiet_NaN(),10).empty());
}
'''
if __name__=='__main__':run('bed_query',code)
