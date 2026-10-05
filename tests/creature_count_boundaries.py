"""Actual native creature-count entry and compatibility helper, engine stand-ins."""
from source_regressions import ROOT, function, run
animation=(ROOT/'src/Registry/Define/Animation.cpp').read_text()
native=(ROOT/'src/Papyrus/sslObject/sslCreatureAnimationSlots.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <limits>
#include <string>
#include <string_view>
#include <vector>
struct VM {void TraceStack(const char*,int){}};using StackID=int;
namespace RE {struct TESQuest{};using BSFixedString=std::string;}
namespace std {template<class...T>string format(const char* text,T...){return text;}}
namespace Registry {
enum Sex {Male,Female};
struct ActorFragment {static constexpr size_t MAX_ACTOR_COUNT=5;};
struct RaceKey {RaceKey(const std::string&){}bool IsValid()const{return true;}bool IsCompatibleWith(RaceKey)const{return true;}};
struct Data {bool IsHuman()const{return false;}bool IsNotSex(Sex s)const{return s==Female;}RaceKey GetRace()const{return RaceKey("Wolf");}};
struct Position {Data data;};
struct TagDetails {TagDetails(const std::vector<std::string_view>&){} };
struct Tags {template<class F>void ForEachExtra(F f)const{f(std::string_view("C"));}};
struct Scene {std::vector<Position> positions{{}};Tags tags;
 bool Legacy_IsCompatibleSexCountCrt(int32_t,int32_t)const;
 bool IsEnabled()const{return true;}bool IsPrivate()const{return false;}
 bool IsCompatibleTags(const TagDetails&)const{return true;}
 std::string id="one";
};
struct Library {static inline int searches=0;static Library* GetSingleton(){static Library l;return &l;}
 template<class F>void ForEachScene(F f){++searches;Scene s;f(&s);}
};
'''+function(animation,'bool Scene::Legacy_IsCompatibleSexCountCrt(')+'\n}\n'
code+=function(native,'std::vector<RE::BSFixedString> GetByRaceGendersTagsImpl(')
code+=r'''
int main(){VM vm;Registry::Scene scene;
 assert(scene.Legacy_IsCompatibleSexCountCrt(1,0));assert(!scene.Legacy_IsCompatibleSexCountCrt(0,1));
 for(int male:{std::numeric_limits<int>::min(),-1,0,1,5,6,std::numeric_limits<int>::max()})
 for(int female:{std::numeric_limits<int>::min(),-1,0,1,5,6,std::numeric_limits<int>::max()}){
  if(male<0||female<0||static_cast<int64_t>(male)+female>5)assert(!scene.Legacy_IsCompatibleSexCountCrt(male,female));
  Registry::Library::searches=0;
  auto result=GetByRaceGendersTagsImpl(&vm,0,nullptr,1,"Wolf",male,female,{});
  if(male<0||female<0||static_cast<int64_t>(male)+female>1){assert(result.empty());assert(Registry::Library::searches==0);}
 }
 assert(GetByRaceGendersTagsImpl(&vm,0,nullptr,1,"Wolf",1,0,{}).size()==1);
}
'''
run('creature_count_boundaries',code)
print('PASS: actual creature count entry/helper reject invalid and extreme integers before arithmetic/search')
