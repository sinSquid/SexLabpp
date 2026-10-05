"""Remaining source contracts: real headers/functions with engine stand-ins.
Papyrus uses the existing limited translator; this is not DLL/VM validation.
"""
from pathlib import Path
import re
from types import SimpleNamespace
from source_regressions import ROOT, function, run
from full_sixth_scripts import helper


def numeric_settings_theme():
    header = (ROOT/'src/Thread/Interface/UI/Theme.h').read_text()
    definitions = header[header.index('    struct ColorValues'):header.index('    inline Data data')]
    fields = re.findall(r'check\(candidate\.(\w+\.\w+), defaults', definitions)
    code = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <initializer_list>
#include "UserData/SettingsValidation.h"
namespace ImGuiMCP {using ImU32=uint32_t;}
#define IM_COL32(r,g,b,a) (uint32_t(r) | (uint32_t(g)<<8) | (uint32_t(b)<<16) | (uint32_t(a)<<24))
'''+definitions+r'''
int main(){
 using SettingsValidation::IsValid;
 for(float v:{NAN,INFINITY,-INFINITY,-1.f,1.e20f}) {
  assert(!IsValid("fVoiceVolume",v));assert(!IsValid("fTimers",std::vector<float>{10,v}));
 }
 assert(IsValid("fTimers",std::vector<float>{10,15,25,7}));assert(!IsValid("fTimers",0.f));
 assert(!IsValid("FMENUSCALEMULT",0.f));assert(IsValid("FMENUSCALEMULT",1.f));
 assert(!IsValid("fSFXVolume",1.1f));assert(IsValid("fSFXVolume",0.f));
 for(const auto* key:{"fDistanceMouth","fDistanceCrotch","fCloseToHeadRatio","fVeryCloseToHeadRatio","fMinTypeDuration","fMinSpeedPenetration","fMaxKissSpeed"}){
  assert(!IsValid(key,0.f));assert(IsValid(key,0.1f));
 }
 for(int v=-10;v<15;++v){
  assert(IsValid("iAskBed",v)==(v>=0&&v<5));
  assert(IsValid("iNPCBed",v)==(v>=0&&v<3));
  assert(IsValid("iClimaxType",v)==(v>=0&&v<3));
 }
 Data d,defaults;d.spacing.md=9.f; Validate(d); assert(d.spacing.md==9.f);
'''
    for field in fields:
        code+=f'for(float invalid:{{NAN,INFINITY,-INFINITY,-1.f,1.e20f}}){{d=defaults;d.{field}=invalid;Validate(d);assert(d.{field}==defaults.{field});}}\n'
    code+='d=defaults; d.offset.dragDistance=0; d.geometry.nestedMenuScale=0; d.fontSize.body=0; Validate(d); assert(d.offset.dragDistance>0 && d.geometry.nestedMenuScale>0 && d.fontSize.body>0);\n}\n'
    run('contract_numeric_settings_theme',code)
    setting=(ROOT/'src/UserData/Settings.cpp').read_text()
    native=(ROOT/'src/Papyrus/sslSystemConfig.cpp').read_text()
    assert 'SettingsValidation::IsValid(a_key, val)' in setting
    assert 'SettingsValidation::IsValid(a_option, value)' in setting
    for name in ('SetSettingInt','SetSettingFlt','SetSettingFltA'):
        body=function(native,'void '+name+'(')
        assert body.index('SettingsValidation::IsValid')<body.index('*s =') if name!='SetSettingFltA' else body.index('SettingsValidation::IsValid')<body.index('(*s)[n] =')
    assert 'Validate(candidate)' in (ROOT/'src/Thread/Interface/UI/Theme.cpp').read_text()


REX = r'''
namespace REX {template<class E>struct EnumSet {
 unsigned bits=0; EnumSet()=default;EnumSet(E v):bits(unsigned(v)){}
 template<class... T>bool all(T... v)const {unsigned m=(unsigned(v)|...);return (bits&m)==m;}
 template<class... T>bool any(T... v)const {return (bits&(unsigned(v)|...))!=0;}
 E get()const{return E(bits);} unsigned underlying()const{return bits;}
};}
'''
RACE = r'''
#define _NODISCARD [[nodiscard]]
#define __fallthrough [[fallthrough]]
namespace RE {
 using BSFixedString=std::string;
 struct TESRace{};
 namespace SEXES {enum SEX{kMale,kFemale};}
 struct Actor {uint8_t race;uint32_t formID=1;};
 struct StaticFunctionTag{};
}
#include "Registry/Define/RaceKey.h"
namespace Registry {
 RaceKey::RaceKey(RE::Actor* a):value(a?Value(a->race):None){}
 RaceKey::RaceKey(const RE::BSFixedString& s):value(s=="Humans"?Human:s=="Dogs"?Dog:s=="Wolves"?Wolf:None){}
 const std::map<RaceKey::Value,RE::BSFixedString> LegacyRaceKeys{{RaceKey::Human,"Humans"},{RaceKey::Dog,"Dogs"},{RaceKey::Wolf,"Wolves"},{RaceKey::Canine,"Canines"}};
}
'''


def race_contracts():
    code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <concepts>
#include <cstdint>
#include <limits>
#include <initializer_list>
#include <map>
#include <string>
#include <type_traits>
#include <vector>
namespace std {template<class...T>string format(const char* s,T&&...){return s;}}
'''+RACE+REX
    race=(ROOT/'src/Registry/Define/RaceKey.cpp').read_text()
    code+='namespace Registry {\n'
    for sig in ('RE::BSFixedString RaceKey::AsString','bool RaceKey::IsCompatibleWith','RaceKey RaceKey::GetMetaRace'):
        code+=function(race,sig)+'\n'
    code+='}\nstruct VM {int errors=0;void TraceStack(const char*,int){++errors;}};\n#define STATICARGS VM* a_vm,int a_stackID,RE::StaticFunctionTag*\n'
    native=(ROOT/'src/Papyrus/SexLabRegistry.cpp').read_text()
    for sig in ('int32_t GetRaceID(','int32_t MapRaceKeyToID(','std::vector<int32_t> GetRaceIDA(','std::vector<int32_t> MapRaceKeyToIDA(','RE::BSFixedString MapRaceIDToRaceKey(','std::vector<RE::BSFixedString> MapRaceIDToRaceKeyA('):
        code+=function(native,sig)+'\n'
    code+='namespace Registry {\n'+re.search(r'enum class Sex : uint8_t\s*\{.*?\};',(ROOT/'src/Registry/Define/Sex.h').read_text(),re.S)[0]+r'''
 struct ActorFragment {
 RaceKey race; float scale=1; REX::EnumSet<Sex> sex{Sex::Male};
 bool vampire=false,unconscious=false,submissive=false;
 RaceKey GetRace()const{return race;} auto GetSex()const{return sex;}
 bool IsVampire()const{return vampire;}bool IsUnconscious()const{return unconscious;}bool IsSubmissive()const{return submissive;}
 int32_t GetCompatibilityScore(const ActorFragment&)const;
 };
}
namespace Settings {int iWeightVampire=10,iWeightSexStrict=100,iWeightSexLight=50,iWeightSexMismatch=-50,iWeightUnconscious=10,iWeightSubmissive=20,iWeightScale=10,iScoreAcceptThreshold=20;float fScaleTolerance=.1;}
namespace Registry {
'''+function((ROOT/'src/Registry/Define/Fragment.cpp').read_text(),'int32_t ActorFragment::GetCompatibilityScore')+'}\n'+r'''
int main(){
 using namespace Registry; VM vm; RE::Actor human{0},invalid{255},dog{RaceKey::Dog};
 assert(GetRaceID(&vm,0,nullptr,nullptr)==0);assert(GetRaceID(&vm,0,nullptr,&human)==0);
 assert(GetRaceIDA(&vm,0,nullptr,nullptr).empty());assert(GetRaceIDA(&vm,0,nullptr,&invalid).empty());
 assert(GetRaceIDA(&vm,0,nullptr,&human)==std::vector<int32_t>{0});
 assert(MapRaceKeyToIDA(&vm,0,nullptr,"Humans")==std::vector<int32_t>{0});
 assert(MapRaceKeyToIDA(&vm,0,nullptr,"bad").empty());
 assert((GetRaceIDA(&vm,0,nullptr,&dog)==std::vector<int32_t>{RaceKey::Dog,RaceKey::Canine}));
 for(int v=0;v<256;++v) assert(RaceKey(RaceKey::Value(v)).IsValid()==(v<=RaceKey::Wolf));
 for(int v:{-256,-1,255,256,269,512,INT32_MAX}) {
  assert(MapRaceIDToRaceKey(nullptr,v).empty());assert(MapRaceIDToRaceKeyA(nullptr,v).empty());
 }
 for(int a=0;a<=RaceKey::Wolf;++a)for(int b=0;b<=RaceKey::Wolf;++b){
  RaceKey x{RaceKey::Value(a)},y{RaceKey::Value(b)};
  assert(x.IsCompatibleWith(y)==y.IsCompatibleWith(x));
  ActorFragment slot{x},actor{y};
  bool expected=a==b || (a==RaceKey::Canine&&(b==RaceKey::Dog||b==RaceKey::Wolf)) ||
   (a==RaceKey::BoarAny&&(b==RaceKey::BoarSingle||b==RaceKey::BoarMounted));
  assert((slot.GetCompatibilityScore(actor)!=0)==expected);
 }
 Settings::iWeightSexStrict=Settings::iWeightVampire=Settings::iWeightUnconscious=Settings::iWeightSubmissive=Settings::iWeightScale=INT32_MAX;
 ActorFragment slot{RaceKey::Human};assert(slot.GetCompatibilityScore(slot)==INT32_MAX);
}
'''
    run('contract_race_and_score',code)


def slr_domains():
    code=r'''
#include <cassert>
#include <concepts>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>
#include <unistd.h>
'''+RACE+REX+r'''
#include "Registry/Util/Decode.h"
namespace Registry {
 enum class Sex:uint8_t{None=0,Male=1,Female=2,Futa=4};
 struct ActorFragment {static constexpr size_t MAX_ACTOR_COUNT=5;ActorFragment(REX::EnumSet<Sex>,RaceKey,float,bool,bool,bool){}};
 struct PositionInfo {ActorFragment data{{},RaceKey::None,1,false,false,false};std::vector<RE::BSFixedString>annotations;PositionInfo(Decode::Reader&,uint8_t);};
}
namespace Registry {
'''+function((ROOT/'src/Registry/Define/Animation.cpp').read_text(),'PositionInfo::PositionInfo')+'}\n'+r'''
void check(uint8_t race,uint8_t sex,uint8_t extra,int32_t scale,bool expected){
 auto p=std::filesystem::temp_directory_path()/std::to_string(getpid());
 {std::ofstream o(p,std::ios::binary);o.put(race);o.put(sex);for(int shift:{24,16,8,0})o.put(uint8_t(uint32_t(scale)>>shift));o.put(extra);}
 bool accepted=true;try{std::ifstream f(p,std::ios::binary);Decode::Reader r(f);Registry::PositionInfo pos(r,4);assert(r.Remaining()==0);}catch(const std::runtime_error&){accepted=false;}
 std::filesystem::remove(p);assert(accepted==expected);
}
int main(){
 for(int r=0;r<256;++r)check(r,1,0,1000,r<=Registry::RaceKey::Wolf);
 for(int s=0;s<256;++s){check(0,s,0,1000,s>0&&s<=7);check(1,s,0,1000,s>0&&s<=3);}
 for(int e=0;e<256;++e)check(0,1,e,1000,e<=7);
 for(int32_t scale:{INT32_MIN,-1,0,1,1000,INT32_MAX})check(0,1,0,scale,scale>0);
}
'''
    run('contract_slr_domains',code)


def excitement_storage():
    store={}; now=[100.]
    def setv(actor,key,value):store[actor,key]=value
    storage=SimpleNamespace(SetFloatValue=setv,SetIntValue=setv,
        HasFloatValue=lambda actor,key:(actor,key)in store,
        GetFloatValue=lambda actor,key:store.get((actor,key),0.),
        GetIntValue=lambda actor,key:store.get((actor,key),0))
    def actor(ref,enj,count):
        return helper('sslActorAlias','StoreExcitementState','arg',{
            '_ActorRef':ref,'_FullEnjoyment':enj,'_OrgasmCount':count,'StorageUtil':storage,
            'SexLabUtil':SimpleNamespace(GetCurrentGameRealTime=lambda:now[0]),
            'PapyrusUtil':SimpleNamespace(ClampInt=lambda v,low,high:max(low,min(high,v))),
        },state_names=('_FullEnjoyment','_OrgasmCount'))
    a,b=actor('same-name-A',80,2),actor('same-name-B',20,1)
    a('Backup');b('Backup');now[0]=130
    a('Restore');b('Restore');assert a.__globals__['_FullEnjoyment']==40 and b.__globals__['_FullEnjoyment']==10
    a.__globals__['_FullEnjoyment']=5;a('Backup');now[0]=140;a('Restore');assert a.__globals__['_FullEnjoyment']==0
    unseen=actor('unseen',11,0);unseen('Restore');assert unseen.__globals__['_FullEnjoyment']==11
    now[0]=90;b('Restore');assert b.__globals__['_FullEnjoyment']==10
    actor(None,80,1)('Backup');assert not any(k[0] is None for k in store)



def scale_division():
    code=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <initializer_list>
namespace logger {template<class... T>void warn(T&&...){} template<class...T>void error(T&&...){} template<class...T>void debug(T&&...){};}
namespace Settings {bool bDisableScale=false;}
namespace RE {
 namespace SEXES {enum SEX{kMale,kFemale};}
 struct TESNPC {SEXES::SEX GetSex(){return SEXES::kMale;}};
 struct Actor{float base=1;TESNPC npc;TESNPC* GetActorBase(){return &npc;}uint32_t GetFormID(){return 1;}};
}
namespace SKEE {
 struct Interface {
 int version=3,writes=0,mutations=0;float output=0,newBase=1;bool remove=false;
 uint32_t GetVersion(){return version;}
 template<class...T>void AddNodeTransformScaleMode(T&&...){++mutations;}
 bool RemoveNodeTransformScale(RE::Actor* actor,bool,bool,const char*,const char*){++mutations;if(remove)actor->base=newBase;return remove;}
 template<class...T>void UpdateNodeTransforms(T&&...){}
 void AddNodeTransformScale(RE::Actor*,bool,bool,const char*,const char*,float v){++writes;output=v;}
 };
 struct INiTransformInterface:Interface{static constexpr uint32_t Version=3;};
 namespace Legacy {
 struct FixedString{FixedString(const char*){}};
 struct OverrideVariant {enum{ScaleMode,Scale};float v=0;void SetInt(int,int){}void SetFloat(int,float x){v=x;}};
 struct INiTransformInterface:Interface {
  template<class... T>bool RemoveNodeTransformComponent(RE::Actor* actor,T&&...){++mutations;if(remove)actor->base=newBase;return remove;}
  void AddNodeTransform(RE::Actor*,bool,bool,FixedString,FixedString,OverrideVariant& v){++mutations;if(v.v!=0){++writes;output=v.v;}}
 };
 }
}
// The stand-ins share the API surface to exercise both control-flow branches.
// Production interface casts remain in the body; ABI/layout is not certified.
struct Both: SKEE::INiTransformInterface {
 using FixedString=SKEE::Legacy::FixedString;using OverrideVariant=SKEE::Legacy::OverrideVariant;
 template<class... T>bool RemoveNodeTransformComponent(RE::Actor* a,T&&...){++mutations;if(remove)a->base=newBase;return remove;}
 void AddNodeTransform(RE::Actor*,bool,bool,FixedString,FixedString,OverrideVariant& v){++mutations;if(v.v!=0){++writes;output=v.v;}}
};
namespace Registry {
 struct RaceKey {enum Value{Human,AshHopper,Chaurus,ChaurusHunter,Chicken,Fox,FrostAtronach,Spider,LargeSpider,GiantSpider,Horker,Mudcrab};Value value=Human;operator Value()const{return value;}};
 struct Scale {
 enum ScaleModes{Multiplicative};const char* basenode="NPC";const char* namekey="SexLabRegistry";Both* transformInterface;
 float GetScale(RE::Actor* a){return a->base;}void SetScale(RE::Actor*,RaceKey,float);
 };
'''
    body=function((ROOT/'src/Registry/Util/Scale.cpp').read_text(),'void Scale::SetScale(RE::Actor* a_actor, RaceKey')
    # Replace only the legacy cast with the common surface stand-in; do not alter
    # guards, conversion or division. Production vtable compatibility is deferred.
    body=body.replace('reinterpret_cast<SKEE::Legacy::INiTransformInterface*>(transformInterface)','static_cast<Both*>(transformInterface)')
    code+=body+'}\n'+r'''
int main(){
 Both plugin;Registry::Scale s; s.transformInterface=&plugin;RE::Actor actor;
 for(int version:{2,3}) {
  plugin.version=version;
  for(float target:{NAN,INFINITY,-INFINITY,-1.f,0.f}){plugin.writes=0;s.SetScale(&actor,{},target);assert(plugin.writes==0);}
  for(float base:{NAN,INFINITY,-INFINITY,-1.f,0.f}){actor.base=base;plugin.writes=0;s.SetScale(&actor,{},2);assert(plugin.writes==0);}
  plugin.remove=true;plugin.newBase=1;actor.base=2;plugin.mutations=0;
  s.SetScale(&actor,{Registry::RaceKey::GiantSpider},std::numeric_limits<float>::max());
  assert(plugin.mutations==0&&actor.base==2);
  s.SetScale(&actor,{Registry::RaceKey::Chaurus},std::numeric_limits<float>::denorm_min());
  assert(plugin.mutations==0&&actor.base==2);
  for(float base:{NAN,INFINITY,-INFINITY,-1.f,0.f}){actor.base=base;plugin.mutations=0;s.SetScale(&actor,{},2);assert(plugin.mutations==0);}
  plugin.remove=false;
  actor.base=2;plugin.writes=0;s.SetScale(&actor,{},1);assert(plugin.writes==1&&plugin.output==.5f);
  actor.base=std::numeric_limits<float>::min();plugin.writes=0;s.SetScale(&actor,{},std::numeric_limits<float>::max());assert(plugin.writes==0);
  plugin.remove=true;plugin.newBase=0;actor.base=1;plugin.writes=0;s.SetScale(&actor,{},2);assert(plugin.writes==0);
  plugin.remove=false;actor.base=1;plugin.writes=0;s.SetScale(&actor,{},1);assert(plugin.writes==0);
  s.SetScale(nullptr,{},1);assert(plugin.writes==0);
 }
}
'''
    run('contract_scale_division',code)


def tag_priority():
    production=(ROOT/'src/Registry/Define/Tags.cpp').read_text()
    code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <bit>
#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <vector>
#define _NODISCARD [[nodiscard]]
namespace RE{using BSFixedString=std::string;}
namespace stl {template<class E>struct enumeration {
 uint64_t bits=0;void set(E v){bits|=uint64_t(v);}void reset(E v){bits&=~uint64_t(v);}
 bool all(E v)const{return (bits&uint64_t(v))==uint64_t(v);}
 bool any(E v)const{return (bits&uint64_t(v))!=0;}
 E get()const{return E(bits);}uint64_t underlying()const{return bits;}
};}
#include "Registry/Define/Tags.h"
namespace Registry {
 static const std::map<RE::BSFixedString,Tag>TagTable{{"Anal",Tag::Anal}};
'''
    for sig in ('void TagData::AddTag(Tag','void TagData::AddTag(RE::BSFixedString','void TagData::RemoveTag(Tag','void TagData::RemoveTag(const TagData&','void TagData::RemoveExtraTag(','void TagData::RemoveAnnotation','bool TagData::HasTag(Tag','bool TagData::HasTag(const RE::BSFixedString','bool TagData::HasTags(','bool TagData::IsEmpty(','bool TagData::HasAnnotation(','void TagData::AddAnnotation(','void TagData::AddExtraTag(','bool TagData::HasExtraTag('):
        code+=function(production,sig)+'\n'
    code+='}\n'+r'''
int main(){
 using namespace Registry;TagData tags;tags.AddAnnotation("Anal");
 assert(tags.HasAnnotation("Anal"));assert(!tags.HasTag("Anal"));assert(!tags.HasTag(Tag::Anal));
 tags.AddTag(Tag::Anal);assert(tags.HasTag("Anal"));tags.RemoveTag(Tag::Anal);
 assert(!tags.HasTag("Anal"));assert(tags.HasAnnotation("Anal"));tags.RemoveAnnotation("Anal");assert(tags.IsEmpty());
 tags.AddAnnotation("custom");assert(tags.HasTag("custom"));
 TagData query(std::vector<std::string>{"custom"});assert(tags.HasTags(query,true));
 TagData base(std::vector<std::string>{"Anal"});assert(!tags.HasTags(base,true));
 tags.AddTag("Anal");assert(tags.HasTags(base,true));
 TagData self;self.AddTag("one");self.AddTag("two");self.AddTag("three");self.AddTag(Tag::Anal);self.AddAnnotation("keep");
 self.RemoveTag(self);assert(!self.HasTag("one")&&!self.HasTag("two")&&!self.HasTag("three"));
 assert(!self.HasTag(Tag::Anal)&&self.HasAnnotation("keep"));
}
'''
    run('contract_tag_priority',code)



def slr_scene_fields():
    production=(ROOT/'src/Registry/Define/Animation.cpp').read_text()
    code=r'''
#include <algorithm>
#include <cassert>
#include <concepts>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <vector>
#include <unistd.h>
namespace std{template<class...T>string format(const char*s,T&&...){return s;}}
'''+RACE+REX+r'''
#include "Registry/Util/Decode.h"
namespace Combinatorics {enum class CResult{Next};template<class T,class F>void ForEachCombination(T&,F){};}
namespace stl {template<class E>struct enumeration {using enum_type=E;E value;enumeration(E v):value(v){}};}
namespace Registry {
 enum class Sex:uint8_t{None=0,Male=1,Female=2,Futa=4};
 struct ActorFragment {
 static constexpr size_t MAX_ACTOR_COUNT=5; REX::EnumSet<Sex> sex; RaceKey race;
 ActorFragment(REX::EnumSet<Sex> s,RaceKey r,float,bool,bool,bool):sex(s),race(r){}
 bool IsHuman()const{return race.Is(RaceKey::Human);}bool IsSex(Sex v)const{return sex.all(v);}
 };
 struct Coordinate {Coordinate()=default;Coordinate(Decode::Reader&r){for(int n=0;n<4;++n)Decode::Read<float>(r);}};
 struct Transform {Transform(Decode::Reader&r){Coordinate c(r);}};
 struct TagData {
 TagData()=default;TagData(std::initializer_list<int>){}
 TagData(Decode::Reader&r){auto n=Decode::Read<uint64_t>(r);for(uint64_t i=0;i<n;++i)Decode::Read<std::string>(r);}
 template<class T>void AddTag(T&&){}
 };
 struct FurnitureType {enum Value:uint32_t{Pillory=1<<26,All=UINT32_MAX};};
 struct Position {enum class StripData:uint8_t{None=0,All=255};RE::BSFixedString event;bool climax;Transform offset;stl::enumeration<StripData>strips;std::vector<RE::BSFixedString>tags;Position(Decode::Reader&,uint8_t);};
 struct Stage {std::string id;std::vector<Position>positions;float fixedlength;std::string navtext;TagData tags;Stage(Decode::Reader&,uint8_t);};
 struct PositionInfo {ActorFragment data{{},RaceKey::None,1,false,false,false};std::vector<RE::BSFixedString>annotations;PositionInfo(Decode::Reader&,uint8_t);};
 struct Scene {
 std::string hash,id,name;bool enabled,allowBed,isPrivate;Stage*start_animation=nullptr;
 std::vector<PositionInfo>positions;std::vector<std::unique_ptr<Stage>>stages;TagData tags;
 std::map<const Stage*,std::vector<const Stage*>>graph;REX::EnumSet<FurnitureType::Value>furnitureTypes;Coordinate furnitureOffset;
 Scene(Decode::Reader&,std::string_view,uint8_t);
 Stage*GetStageByID(const char*id){for(auto&s:stages)if(s->id==id)return s.get();return nullptr;}
 };
'''
    for sig in ('PositionInfo::PositionInfo','Position::Position','Stage::Stage','Scene::Scene'):
        start=production.index(sig)
        brace=production.index('\n    {',start)+5
        depth,end=1,brace+1
        while depth:
            depth+=(production[end]=='{')-(production[end]=='}');end+=1
        code+=production[start:end]+'\n'
    code+='}\n'+r'''
void integer(std::ofstream&o,uint64_t v,int bytes){for(int n=bytes-1;n>=0;--n)o.put(uint8_t(v>>(8*n)));}
void text(std::ofstream&o,std::string s){integer(o,s.size(),8);o.write(s.data(),s.size());}
void check(int version,uint32_t furniture,int bed,int privacy,int duration,bool expected,int climax=0,int strip=0){
 auto path=std::filesystem::temp_directory_path()/("slr-contract-"+std::to_string(getpid()));
 {std::ofstream o(path,std::ios::binary);
  o<<"Scene001";text(o,"scene");integer(o,1,8); // position count
  o.put(0);o.put(1);integer(o,1000,4);o.put(0);
  if(version>1&&version<4)integer(o,0,8);
  if(version<4)o<<"Stage001";
  integer(o,1,8);o<<"Stage001";integer(o,1,8);
  text(o,"event");o.put(climax);for(int i=0;i<4;++i)integer(o,0,4);o.put(strip);
  if(version==3)o.put(0);if(version>=4)integer(o,0,8);
  integer(o,uint32_t(duration),4);text(o,"next");integer(o,0,8);
  integer(o,1,8);o<<"Stage001";integer(o,0,8);
  integer(o,furniture,4);o.put(bed);for(int i=0;i<4;++i)integer(o,0,4);o.put(privacy);
 }
 bool accepted=true;try{std::ifstream f(path,std::ios::binary);Decode::Reader r(f);Registry::Scene s(r,"hash",version);assert(r.Remaining()==0);}catch(const std::runtime_error&){accepted=false;}
 std::filesystem::remove(path);assert(accepted==expected);
}
int main(){
 for(int v=1;v<=4;++v){
  check(v,0,0,0,0,true);check(v,UINT32_MAX,1,1,1000,true);
  check(v,0,2,0,1000,false);check(v,0,0,2,1000,false);check(v,0,0,0,-1,false);
  for(int bit=0;bit<32;++bit)check(v,uint32_t(1)<<bit,0,0,0,bit<=26);
  // Preserve wire compatibility for noncanonical climax and reserved strip bits.
  for(int byte=0;byte<256;++byte)check(v,0,0,0,0,true,byte,byte);
 }
}
'''
    run('contract_slr_scene_fields',code)



def assignment_score_totals():
    code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <limits>
#include <vector>
namespace RE{struct Actor{int index;};}
namespace Registry {
 struct ActorFragment {static constexpr int MAX_ACTOR_COUNT=5;RE::Actor*actor=nullptr;std::vector<int32_t>scores;int32_t GetCompatibilityScore(const ActorFragment&a)const{return scores.at(a.actor->index);}RE::Actor*GetActor()const{return actor;}};
 struct Position{ActorFragment data;};
 struct Scene{std::vector<Position>positions;std::vector<std::vector<RE::Actor*>>FindAssignments(const std::vector<ActorFragment>&)const;};
'''+function((ROOT/'src/Registry/Define/Animation.cpp').read_text(),'std::vector<std::vector<RE::Actor*>> Scene::FindAssignments')+'}\n'+r'''
int main(){
 RE::Actor a{0},b{1};std::vector<Registry::ActorFragment>actors{{&a,{}},{&b,{}}};
 Registry::Scene s{{{{nullptr,{INT32_MAX,100}}},{{nullptr,{101,INT32_MAX}}}}};
 auto sorted=s.FindAssignments(actors);assert(sorted.size()==2);assert(sorted[0][0]==&a&&sorted[0][1]==&b);
 // Negative scores are still ordered by their true sum, with no signed wrap.
 s.positions[0].data.scores={INT32_MIN,-100};s.positions[1].data.scores={-101,INT32_MIN};
 sorted=s.FindAssignments(actors);assert(sorted[0][0]==&b&&sorted[0][1]==&a);
}
'''
    run('contract_assignment_score_totals',code)


if __name__=='__main__':
    for test in (numeric_settings_theme,race_contracts,slr_domains,excitement_storage,scale_division,tag_priority,slr_scene_fields,assignment_score_totals):
        test();print('PASS:',test.__name__)
