"""Real native data functions with engine stand-ins; expected behavior, not source-shape checks."""
from review_native_data_support import ROOT, function, run
import re
import subprocess

COMMON = r'''
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cmath>
#include <compare>
#include <concepts>
#include <cstdint>
#include <fstream>
#include <format>
#include <functional>
#include <iostream>
#include <limits>
#include <map>
#include <numbers>
#include <ranges>
#include <regex>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>
#define _NODISCARD [[nodiscard]]
#define __fallthrough [[fallthrough]]
using StackID = int;
struct VM { void TraceStack(const char*, int) {} };
namespace logger { template<class... T> void error(T&&...){} }
'''


fragment = COMMON + r'''
#include <bitset>
namespace RE { struct Actor {}; struct TESRace {}; using BSFixedString=std::string;
namespace SEXES { enum SEX { kMale, kFemale, kNone=-1 }; } }
#include "REX/REX/EnumSet.h"
#include "Registry/Define/Fragment.h"
struct Settings {
#define INI_SETTING(name, value, category) static inline auto name = value;
'''
setting_source = (ROOT / 'src/UserData/config.def').read_text()
for line in setting_source.splitlines():
    if re.match(r'INI_SETTING\((iScoreAcceptThreshold|iWeight|fScaleTolerance)', line):
        fragment += line + '\n'
fragment += r'''
#undef INI_SETTING
};
namespace Registry {
'''
fragment += function('src/Registry/Define/Fragment.cpp', 'ActorFragment::Value RaceKeyToValue(')
fragment += function('src/Registry/Define/Fragment.cpp', 'ActorFragment::ActorFragment(REX::EnumSet<Sex>')
for signature in ('RaceKey ActorFragment::GetRace()', 'REX::EnumSet<Sex> ActorFragment::GetSex()', 'int32_t ActorFragment::GetCompatibilityScore('):
    fragment += function('src/Registry/Define/Fragment.cpp', signature)
fragment += r'''
struct PositionInfo { ActorFragment data; PapyrusSex GetSexPapyrus() const; };
'''
fragment += function('src/Registry/Define/Animation.cpp', 'PapyrusSex PositionInfo::GetSexPapyrus()')
fragment += r'''
struct TagData {
 std::vector<std::string> tags;
 void ForEachExtra(std::function<bool(std::string_view)> visitor)const {for(auto& t:tags)if(visitor(t))return;}
};
struct Scene { std::vector<PositionInfo> positions; TagData tags;
 bool Legacy_IsCompatibleSexCountCrt(int32_t,int32_t)const; };
'''
fragment += function('src/Registry/Define/Animation.cpp', 'bool Scene::Legacy_IsCompatibleSexCountCrt(')
fragment += r'''
}
int main(){
 using namespace Registry;
 ActorFragment femaleBear({Sex::Female},RaceKey::Bear,1,false,false,false);
 ActorFragment maleBear({Sex::Male},RaceKey::Bear,1,false,false,false);
 ActorFragment femaleHuman({Sex::Female},RaceKey::Human,1,false,false,false);
 ActorFragment maleHuman({Sex::Male},RaceKey::Human,1,false,false,false);
 if(femaleHuman.GetCompatibilityScore(maleHuman)!=0)return 2;
 auto score=femaleBear.GetCompatibilityScore(maleBear);
 auto sex=femaleBear.GetSex().underlying();
 std::cout << "ND-03 Female Bear sex: expected 2, actual " << unsigned(sex)
           << "; male filling female Bear score: expected 0, actual " << score << '\n';
 PositionInfo either{ActorFragment({Sex::Male,Sex::Female},RaceKey::Bear,1,false,false,false)};
 auto papyrus=static_cast<int>(either.GetSexPapyrus());
 std::cout << "ND-19 Either-sex creature mask: expected 24, actual " << papyrus << '\n';
 Scene onlyMale{{PositionInfo{maleBear}},{{"C"}}};
 Scene onlyFemale{{PositionInfo{femaleBear}},{{"C"}}};
 Scene eitherScene{{either},{{"C"}}};
 bool maleCount=onlyMale.Legacy_IsCompatibleSexCountCrt(1,0);
 bool femaleCount=onlyFemale.Legacy_IsCompatibleSexCountCrt(0,1);
 bool eitherCount=eitherScene.Legacy_IsCompatibleSexCountCrt(1,0);
 std::cout << "ND-02 Valid count cases expected 1,1,1; actual " << maleCount << ',' << femaleCount << ',' << eitherCount << '\n';
 if(sex==2 && score==0 && papyrus==24 && maleCount && femaleCount && eitherCount)return 0;
 return 2;
}
'''


creature = COMMON + r'''
#include "Util/Assignment.h"
namespace RE {
 struct TESQuest{};struct TESRace{};using BSFixedString=std::string;
 namespace SEXES {enum SEX{kMale,kFemale,kNone=-1};}
 struct Actor{int race;};
}
#include "Registry/Define/RaceKey.h"
namespace Registry {
 RaceKey::RaceKey(RE::Actor* actor):value(static_cast<Value>(actor->race)){}
'''
creature += function('src/Registry/Define/RaceKey.cpp','bool RaceKey::IsCompatibleWith(')
creature += r'''
 struct ActorFragment{static constexpr size_t MAX_ACTOR_COUNT=5;};
 struct TagDetails {TagDetails(const std::vector<std::string_view>&){} };
 struct Data {RaceKey race;RaceKey GetRace()const{return race;}};
 struct Position{Data data;};
 struct Scene{std::vector<Position> positions;std::string id="scene";
  bool IsEnabled()const{return true;}bool IsPrivate()const{return false;}
  bool IsCompatibleTags(const TagDetails&)const{return true;}};
 struct Library {Scene scene;static Library* GetSingleton(){static Library x;return &x;}
  void ForEachScene(std::function<bool(const Scene*)> callback){callback(&scene);}};
}
'''
creature += function('src/Papyrus/sslObject/sslCreatureAnimationSlots.cpp', 'std::vector<RE::BSFixedString> GetByCreatureActorsTagsImpl(')
creature += r'''
int main(){
 VM vm;RE::Actor dog{Registry::RaceKey::Dog},wolf{Registry::RaceKey::Wolf};
 auto& scene=Registry::Library::GetSingleton()->scene;
 scene.positions={{{Registry::RaceKey::Canine}},{{Registry::RaceKey::Dog}}};
 auto bad=GetByCreatureActorsTagsImpl(&vm,0,nullptr,2,{&dog,&wolf},{});
 auto control=GetByCreatureActorsTagsImpl(&vm,0,nullptr,2,{&wolf,&dog},{});
 if(control!=std::vector<std::string>{"scene"})return 2;
 std::cout << "ND-04 Same [Canine,Dog] scene: [Dog,Wolf] expected 1 match, actual " << bad.size()
           << "; reordered control has " << control.size() << " match\n";
 return bad==control?0:2;
}
'''


partners = COMMON + r'''
namespace RE {struct TESQuest{};struct TESObjectREFR{};using BSFixedString=std::string;
 struct Actor:TESObjectREFR{int sex;explicit Actor(int s):sex(s){}};
 struct PlayerCharacter:Actor{PlayerCharacter():Actor(0){}static Actor* GetSingleton(){static PlayerCharacter p;return &p;}};}
enum LegacySex {Male=0,Female,CrtMale,CrtFemale,None=-1};
LegacySex GetLegacySex(RE::Actor* actor){return static_cast<LegacySex>(actor->sex);}
std::vector<RE::Actor*> available;
std::vector<RE::Actor*> FindAvailableActors(VM*,StackID,RE::TESQuest*,RE::TESObjectREFR*,float,LegacySex,
 RE::Actor*,RE::Actor*,RE::Actor*,RE::Actor*,const char*){return available;}
'''
partners += function('src/Papyrus/sslLibrary/LegacyData.h', 'inline std::array<int32_t, 4> GetLegacySex(std::vector<RE::Actor*>')
partners += function('src/Papyrus/sslLibrary/sslThreadLibrary.cpp', 'std::vector<RE::Actor*> FindAvailablePartners(')
partners += r'''
int main(){
 VM vm;RE::Actor female(Female),male(Male);
 available={&female,&male};auto bad=FindAvailablePartners(&vm,0,nullptr,{},2,1,1,100);
 available={&male,&female};auto control=FindAvailablePartners(&vm,0,nullptr,{},2,1,1,100);
 if(control.size()!=2)return 2;
 std::cout << "ND-05 Need one male and one female: [F,M] expected 2, actual " << bad.size()
           << "; [M,F] control actual " << control.size() << '\n';
 return bad.size()==2 ? 0:2;
}
'''


bedroll = COMMON + r'''
namespace glm {float radians(float degrees){return degrees*std::numbers::pi_v<float>/180.0f;}
struct vec3{float x,y,z;vec3(float X,float Y,float Z):x(X),y(Y),z(Z){}
 vec3& operator+=(const vec3& v){x+=v.x;y+=v.y;z+=v.z;return *this;}};}
namespace Registry {
 struct Coordinate {glm::vec3 location;float rotation;
  Coordinate(float,float,float,float);Coordinate(const std::vector<float>&);
  void Apply(Coordinate&)const;Coordinate ApplyReturn(const Coordinate&)const;};
'''
for signature in ('Coordinate::Coordinate(float a_x', 'Coordinate::Coordinate(const std::vector<float>&',
                  'void Coordinate::Apply(', 'Coordinate Coordinate::ApplyReturn('):
    bedroll += function('src/Registry/Define/Transform.cpp', signature)
bedroll += r'''
 struct FurnitureType {enum Value{BedRoll=1};};
 struct FurnitureDetails {Coordinate offset;
  FurnitureDetails(FurnitureType::Value,Coordinate c):offset(c){} };
'''
library_header = (ROOT / 'src/Registry/Library.h').read_text()
bedroll += next(line.strip() for line in library_header.splitlines() if 'FurnitureDetails offsetDefaultBedroll' in line) + '\n'
bedroll += r'''
}
int main(){
 using namespace Registry;
 auto result=offsetDefaultBedroll.offset.ApplyReturn(Coordinate(0,0,0,0));
 auto control=Coordinate(0,0,7.5,std::numbers::pi_v<float>).ApplyReturn(Coordinate(0,0,0,0));
 if(std::abs(control.rotation-std::numbers::pi_v<float>)>0.0001f)return 2;
 std::cout << "ND-08 Default bedroll applied rotation: expected " << std::numbers::pi_v<float>
           << " rad, actual " << result.rotation << " rad; normalized degrees "
           << std::fmod(result.rotation,2*std::numbers::pi_v<float>)*180/std::numbers::pi_v<float> << '\n';
 return std::abs(result.rotation-std::numbers::pi_v<float>)<0.0001f ? 0:2;
}
'''


tags = COMMON + r'''
namespace RE {using BSFixedString=std::string;}
using FixedStringCompare=std::less<std::string>;
namespace stl {template<class E> struct enumeration {
 using U=std::underlying_type_t<E>;U value{};
 E get()const{return static_cast<E>(value);}U underlying()const{return value;}
 void set(E e){value|=static_cast<U>(e);}void reset(E e){value&=~static_cast<U>(e);}
 bool all(E e)const{return (value&static_cast<U>(e))==static_cast<U>(e);}
 bool any(E e)const{return (value&static_cast<U>(e))!=0;}
 enumeration operator&(enumeration b)const{return {value&b.value};}
};}
#include "Registry/Util/Decode.h"
#include "Util/StringUtil.h"
#include "Registry/Define/Tags.h"
'''
tags += re.sub(r'^#include.*$', '', (ROOT / 'src/Registry/Define/Tags.cpp').read_text(), flags=re.M)
tags += r'''
int main(){
 Registry::TagData value;value.AddAnnotation("Anal");value.AddAnnotation("custom");
 if(!value.HasAnnotation("Anal") || !value.HasTag("custom"))return 2;
 Registry::TagDetails required("Anal");
 std::cout << "ND-12 Annotated Anal: HasAnnotation=" << value.HasAnnotation("Anal")
           << "; HasTag expected 1 actual " << value.HasTag("Anal")
           << "; MatchTags expected 1 actual " << required.MatchTags(value) << '\n';
 return value.HasTag("Anal") && required.MatchTags(value) ? 0:2;
}
'''



def main():
    failures=[]
    for name,code,flags in [('fragment_and_creature_sex',fragment,['-ftrivial-auto-var-init=pattern']),
                            ('creature_assignment',creature,[]),('partner_candidates',partners,[]),
                            ('bedroll_rotation',bedroll,[]),('builtin_tag_annotation',tags,[])]:
        try: run(name,code,flags)
        except subprocess.CalledProcessError: failures.append(name)
    if failures: raise AssertionError('Contract failures: '+', '.join(failures))

if __name__ == '__main__': main()
