"""Compile production algorithms with minimal engine stand-ins (not game tests).

REGISTRY_TEST_BASELINE=HEAD runs the same cases against a prior Git snapshot.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('REGISTRY_TEST_BASELINE')


def read(path):
    if BASE:
        return subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8')


def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


PREAMBLE = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <functional>
#include <format>
#include <memory>
#include <map>
#include <queue>
#include <set>
#include <shared_mutex>
#include <string>
#include <utility>
#include <vector>
using namespace std;
namespace RE {struct StaticFunctionTag{}; using BSFixedString=string;}
'''

animation = read('src/Registry/Define/Animation.cpp')
util = read('src/Papyrus/SexLabUtil.cpp')
library = read('src/Papyrus/sslLibrary/sslThreadLibrary.cpp')
registry = read('src/Papyrus/SexLabRegistry.cpp')
groups = {}
groups['paths'] = PREAMBLE + r'''
struct Stage{};
struct Scene {
 enum class NodeType{Root,Default,Sink};
 const Stage* root=nullptr;
 map<const Stage*,vector<const Stage*>> graph;
 NodeType GetStageNodeType(const Stage* p)const {return p==root?NodeType::Root:graph.at(p).empty()?NodeType::Sink:NodeType::Default;}
 vector<const Stage*> GetLongestPath(const Stage*)const;
 vector<const Stage*> GetShortestPath(const Stage*)const;
};
''' + function(animation, 'std::vector<const Stage*> Scene::GetLongestPath(') + function(animation, 'std::vector<const Stage*> Scene::GetShortestPath(') + r'''
int main(){
 Stage a,b,c,d,e,f;
 Scene s;s.root=&a;s.graph={{&a,{&b}},{&b,{}}};
 assert((s.GetShortestPath(&a)==vector<const Stage*>{&a,&b}));
 assert((s.GetShortestPath(&b)==vector<const Stage*>{&b}));
 s.graph[&a]={};assert((s.GetLongestPath(&a)==vector<const Stage*>{&a}));
 assert((s.GetShortestPath(&a)==vector<const Stage*>{&a}));
 s.graph={{&a,{&b,&c}},{&b,{&d}},{&c,{&e}},{&e,{&d}},{&d,{&f}},{&f,{}}};
 assert((s.GetLongestPath(&a)==vector<const Stage*>{&a,&c,&e,&d,&f}));
 assert((s.GetShortestPath(&a)==vector<const Stage*>{&a,&b,&d,&f}));
 s.graph={{&a,{&b}},{&b,{&a,&c}},{&c,{}}};
 assert((s.GetLongestPath(&a)==vector<const Stage*>{&a,&b,&c}));
 assert((s.GetShortestPath(&a)==vector<const Stage*>{&a,&b,&c}));
 s.graph[&b]={&a};assert(s.GetShortestPath(&a).empty());assert(s.GetLongestPath(&a).empty());
 // Forty diamonds have 2^40 routes but only121 vertices. DAG suffixes must be cached.
 array<Stage,121> nodes;Scene diamonds;diamonds.root=&nodes[0];
 for(size_t i=0;i<40;++i){const auto j=i*3;diamonds.graph[&nodes[j]]={&nodes[j+1],&nodes[j+2]};
  diamonds.graph[&nodes[j+1]]={&nodes[j+3]};diamonds.graph[&nodes[j+2]]={&nodes[j+3]};}
 diamonds.graph[&nodes[120]]={};assert(diamonds.GetLongestPath(&nodes[0]).size()==81);
}
'''
groups['extrema'] = PREAMBLE + '\n'.join(function(util, sig) for sig in (
    'int IntMinMaxIndex(', 'int IntMinMaxValue(', 'int FloatMinMaxIndex(', 'float FloatMinMaxValue(')) + r'''
int main(){
 assert(IntMinMaxIndex(nullptr,{4,1},false)==1);
 assert(FloatMinMaxIndex(nullptr,{-4.f,-1.f},true)==1);
 assert(IntMinMaxValue(nullptr,{4,1},false)==1);
 assert(FloatMinMaxValue(nullptr,{-4.f,-1.f},true)==-1);
 assert(IntMinMaxIndex(nullptr,{},true)==0);
 assert(IntMinMaxIndex(nullptr,{3,3},true)==0);
 assert(FloatMinMaxIndex(nullptr,{3,-4,0},false)==1);
}
'''

groups['partners'] = PREAMBLE + r'''
namespace RE { struct TESQuest{}; struct TESObjectREFR{}; struct Actor{int id;}; }
struct VM{void TraceStack(const char*,int){}};using StackID=int;
enum class LegacySex{None};
namespace Registry {
struct Position {set<int> ids;bool CanFillPosition(RE::Actor*a)const{return ids.contains(a->id);}};
struct Scene{vector<Position> positions;};
struct Library {Scene* scene=nullptr;static Library*GetSingleton(){static Library l;return &l;}
 const Scene*GetSceneById(string id){return id=="valid"?scene:nullptr;}};
}
vector<RE::Actor*> available;
vector<RE::Actor*> FindAvailableActors(VM*,StackID,RE::TESQuest*,RE::TESObjectREFR*,float,LegacySex,
 RE::Actor*a,RE::Actor*b,RE::Actor*c,RE::Actor*d,string){auto v=available;erase_if(v,[&](auto*p){return p==a||p==b||p==c||p==d;});return v;}
''' + function(library, 'std::vector<RE::Actor*> FindAnimationPartnersImpl(') + r'''
int main(){
 VM vm;RE::TESObjectREFR center;RE::Actor a{1},b{2},c{3};
 Registry::Scene scene{{{{1}},{{2}}}};Registry::Library::GetSingleton()->scene=&scene;
 available={&a,&b};
 assert((FindAnimationPartnersImpl(&vm,0,nullptr,"valid",&center,10,{&a})==vector<RE::Actor*>{&a,&b}));
 assert((FindAnimationPartnersImpl(&vm,0,nullptr,"valid",&center,10,{})==vector<RE::Actor*>{&a,&b}));
 available={&a};assert(FindAnimationPartnersImpl(&vm,0,nullptr,"valid",&center,10,{}).empty());
 assert(FindAnimationPartnersImpl(&vm,0,nullptr,"invalid",&center,10,{}).empty());
 scene.positions={{{1,2}},{{1,2}}};available={&b};
 assert((FindAnimationPartnersImpl(&vm,0,nullptr,"valid",&center,10,{&a,&a})==vector<RE::Actor*>{&a,&b}));
 // Fifth include is also in the search result; never fill two positions with it.
 available={&a,&b};
 assert((FindAnimationPartnersImpl(&vm,0,nullptr,"valid",&center,10,{nullptr,nullptr,nullptr,nullptr,&a})==vector<RE::Actor*>{&a,&b}));
}
'''

groups['sentinel'] = PREAMBLE + r'''
struct VM{int errors=0;void TraceStack(const char*,int){++errors;}};
struct Position{bool climax;};struct Stage{string id;vector<Position> positions;};
struct Scene{vector<int>positions{0,1};vector<Stage*> stages;auto GetClimaxStages()const{return stages;}};
Scene* scene;
#define STATICARGS VM* a_vm,int a_stackID,RE::StaticFunctionTag*
#define SCENE(ret) if(!scene)return ret
''' + function(registry, 'std::vector<RE::BSFixedString> GetClimaxStages(') + r'''
int main(){VM vm;Scene s;scene=&s;Stage a{"A",{{false},{true}}},b{"B",{{true},{false}}};s.stages={&a,&b};
 assert((GetClimaxStages(&vm,0,nullptr,"",-1)==vector<string>{"A","B"}));
 assert((GetClimaxStages(&vm,0,nullptr,"",0)==vector<string>{"B"}));
 assert(GetClimaxStages(&vm,0,nullptr,"",-2).empty());assert(GetClimaxStages(&vm,0,nullptr,"",2).empty());
 assert(vm.errors==2);
}
'''

groups['race_array'] = PREAMBLE + r'''
namespace RE{struct Actor{int race;};}
struct VM{void TraceStack(const char*,int){}};
namespace Registry{struct RaceKey{
 enum Value{Human=0,Dog=1,Canine=2,None=255};Value value;
 RaceKey(Value v):value(v){} RaceKey(RE::Actor*a):value(static_cast<Value>(a->race)){}
 RaceKey(const string&s):value(s=="Human"?Human:s=="Dog"?Dog:None){}
 bool IsValid()const{return value!=None;}explicit operator int32_t()const{return value;}
 RaceKey GetMetaRace()const{return value==Dog?Canine:None;}
};}
#define STATICARGS VM* a_vm,int a_stackID,RE::StaticFunctionTag*
int GetRaceID(VM*,int,RE::StaticFunctionTag*,RE::Actor*a){return a?a->race:0;}
int MapRaceKeyToID(VM*,int,RE::StaticFunctionTag*,string s){return s=="Dog"?1:0;}
''' + function(registry, 'std::vector<int32_t> GetRaceIDA(') + function(registry, 'std::vector<int32_t> MapRaceKeyToIDA(') + r'''
int main(){VM vm;RE::Actor a{0};assert((GetRaceIDA(&vm,0,nullptr,&a)==vector<int32_t>{0}));
 assert((MapRaceKeyToIDA(&vm,0,nullptr,"Human")==vector<int32_t>{0}));
 assert((MapRaceKeyToIDA(&vm,0,nullptr,"Dog")==vector<int32_t>{1,2}));
 assert(MapRaceKeyToIDA(&vm,0,nullptr,"invalid").empty());assert(GetRaceIDA(&vm,0,nullptr,nullptr).empty());
}
'''

SEARCH = PREAMBLE + r'''
namespace RE {
 enum class FormType{Furniture};
 struct Point {float x=0,y=0,z=0;float GetDistance(Point p)const{return sqrt((x-p.x)*(x-p.x)+(y-p.y)*(y-p.y)+(z-p.z)*(z-p.z));}};
 struct Base {bool furniture=true;bool Is(FormType)const{return furniture;}};
 struct TESObjectREFR {Point p;Base base;int bed=0;Point GetPosition()const{return p;}Base*GetBaseObject(){return &base;}};
 struct Actor:TESObjectREFR{bool valid=true;int sex=0;};struct TESQuest{};
 struct Handle{shared_ptr<Actor>p;shared_ptr<Actor>get()const{return p;}};
 struct ProcessLists{vector<Handle>highActorHandles;static ProcessLists*GetSingleton(){static ProcessLists p;return &p;}};
 namespace BSContainer{enum class ForEachResult{kContinue};}using VMStackID=int;
}
struct VM{void TraceStack(const char*,int){}};using StackID=int;
enum LegacySex {None=-1,Male=0,Female=1,CrtMale=2,CrtFemale=3};
LegacySex GetLegacySex(RE::Actor*a){return LegacySex(a->sex);}
namespace Settings{bool bCreatureGender=true;}
namespace Registry {
 struct RaceKey{enum Value{Human};RaceKey(const string&){}RaceKey(RE::Actor*){}bool Is(Value)const{return true;}bool IsCompatibleWith(RaceKey)const{return true;}};
 bool IsValidActor(RE::Actor*a){return a->valid;}
 struct FurnitureType {enum Value{None=0,BedRoll=1,BedSingle=2,BedDouble=4};Value value;
 bool Is(Value v)const{return value==v;}static FurnitureType GetBedType(RE::TESObjectREFR*p){return{Value(p->bed)};}
 static bool IsBedType(RE::TESObjectREFR*p){return p->bed!=0;}};
}
vector<RE::TESObjectREFR*> refs;
namespace Util{void ForEachObjectInRange(RE::TESObjectREFR*,float,function<RE::BSContainer::ForEachResult(RE::TESObjectREFR*)>f){for(auto*r:refs)f(r);}}
'''
groups['beds'] = SEARCH + function(library, 'std::vector<RE::TESObjectREFR*> FindBeds(') + function(library, 'int32_t GetBedTypeImpl(') + r'''
int main(){VM vm;RE::TESObjectREFR center,a,b,c;a.bed=1;b.bed=2;c.bed=4;
 a.p={1,0,100};b.p={2,0,600};c.p={3,0,-600};refs={&a,&b,&c};
 assert((FindBeds(&vm,0,nullptr,&center,1000,512)==vector<RE::TESObjectREFR*>{&a}));
 refs.push_back(nullptr);
 assert(FindBeds(&vm,0,nullptr,&center,1000,0).size()==3);
 assert(GetBedTypeImpl(&vm,0,nullptr,&a)==1);assert(GetBedTypeImpl(&vm,0,nullptr,&b)==2);assert(GetBedTypeImpl(&vm,0,nullptr,&c)==3);
 assert(GetBedTypeImpl(&vm,0,nullptr,&center)==0);
}
'''
groups['radius'] = SEARCH + function(library, 'std::vector<RE::Actor*> FindAvailableActors(') + r'''
int main(){VM vm;RE::TESObjectREFR center;center.p={100,100,100};
 auto a=make_shared<RE::Actor>();a->p={100,100,110};auto b=make_shared<RE::Actor>();b->p={100,100,121};
 RE::ProcessLists::GetSingleton()->highActorHandles={{a},{b}};
 assert((FindAvailableActors(&vm,0,nullptr,&center,20,None,nullptr,nullptr,nullptr,nullptr,"")==vector<RE::Actor*>{a.get()}));
 assert(FindAvailableActors(&vm,0,nullptr,&center,0,None,nullptr,nullptr,nullptr,nullptr,"").empty());
 a->valid=false;assert(FindAvailableActors(&vm,0,nullptr,&center,20,None,nullptr,nullptr,nullptr,nullptr,"").empty());
 a->valid=true;assert(FindAvailableActors(&vm,0,nullptr,&center,20,None,a.get(),nullptr,nullptr,nullptr,"").empty());
}
'''

model = read('src/Papyrus/sslThreadModel.cpp')
role_loop = model[model.index('        int sub = 0;'):model.index('            switch (sub)')]
groups['role_order'] = PREAMBLE + r'''
namespace RE {struct Actor{bool IsHumanoid(){return true;}};}
namespace Registry{enum class Sex{Male,Female,Futa};Sex GetSex(RE::Actor*){return Sex::Male;}}
struct Pos {bool submissive;bool IsSubmissive()const{return submissive;}};
struct Scene {vector<Pos>positions;const Pos*GetNthPosition(size_t i)const{return &positions[i];}};
struct Stats{enum{PartnersMale,PartnersFemale,PartnersFuta,PartnersCreature};void AddStatistic(int,int){}};
int Role(RE::Actor*a_actor,const vector<RE::Actor*>&a_positions,Scene*scene){Stats stats;
''' + role_loop + r'''
 return sub;
}
int main(){RE::Actor a,b;Scene first{{{true},{false}}},second{{{false},{true}}};
 assert(Role(&b,{&a,&b},&first)==-1);assert(Role(&b,{&b,&a},&second)==-1);
 assert(Role(&a,{&a,&b},&first)==1);assert(Role(&a,{&b,&a},&second)==1);
}
'''

definitions = read('src/Registry/Library.cpp')
groups['enabled_selectors'] = PREAMBLE + r'''
struct TagDetails{bool MatchTags(int)const{return true;}};
struct RaceKey{};
struct Voice{bool enabled;int tags=0;bool HasRace(RaceKey)const{return true;}};
struct Expression{bool enabled;bool IsEnabled()const{return enabled;}int GetTags()const{return 0;}};
namespace Random{template<class T>T draw(const vector<T>&v){return v.front();}}
struct Library{mutable shared_mutex _mVoice,_mExpressions;map<string,Voice>voices;map<string,Expression>expressions;
 const Voice*GetVoice(const TagDetails&)const;const Voice*GetVoice(RaceKey)const;const Expression*GetExpression(const TagDetails&)const;};
''' + function(definitions, 'const Voice* Library::GetVoice(const TagDetails&') + function(definitions, 'const Voice* Library::GetVoice(RaceKey') + function(definitions, 'const Expression* Library::GetExpression(') + r'''
int main(){Library l;l.voices.emplace("A",Voice{false});l.voices.emplace("B",Voice{true});
 l.expressions.emplace("A",Expression{false});l.expressions.emplace("B",Expression{true});
 assert(l.GetVoice(TagDetails{})->enabled);assert(l.GetVoice(RaceKey{})->enabled);assert(l.GetExpression(TagDetails{})->enabled);
 l.voices.at("B").enabled=false;l.expressions.at("B").enabled=false;
 assert(!l.GetVoice(TagDetails{})&&!l.GetVoice(RaceKey{})&&!l.GetExpression(TagDetails{}));
}
'''

groups['offset_result'] = PREAMBLE + r'''
struct VM{int errors=0;void TraceStack(const char*,int){++errors;}};
namespace Registry{struct Offset{int resets=0;void ResetOffset(){++resets;}};
 struct Position{Offset offset;};struct Stage{vector<Position>positions{1};};
 struct Scene{vector<int>positions{1};Stage stage;Stage*GetStageByID(string s){return s=="good"?&stage:nullptr;}};
 struct Library{Scene scene;static Library*GetSingleton(){static Library l;return &l;}
 bool EditScene(string id,function<void(Scene*)> f){if(id!="good")return false;f(&scene);return true;}};}
#define STATICARGS VM* a_vm,int a_stackID,RE::StaticFunctionTag*
#define POSITION(ret) if(n<0||static_cast<size_t>(n)>=scene->positions.size()){a_vm->TraceStack("bad",a_stackID);return ret;}
''' + function(registry, 'void ResetStageOffset(') + r'''
int main(){VM vm;ResetStageOffset(&vm,0,nullptr,"good","good",0);assert(vm.errors==0);
 assert(Registry::Library::GetSingleton()->scene.stage.positions[0].offset.resets==1);
 ResetStageOffset(&vm,0,nullptr,"bad","good",0);assert(vm.errors==1);
}
'''

stats = read('src/Registry/Stats.cpp')
groups['encounter_init_reset'] = PREAMBLE + r'''
#include <new>
#include <cstring>
#define __fallthrough [[fallthrough]]
namespace RE{using FormID=uint32_t;enum class FormType{ActorCharacter};struct Actor{uint32_t formID;int race;
 uint32_t GetFormID()const{return formID;}bool IsNot(FormType)const{return race<0;}};
 struct Calendar{static Calendar*GetSingleton(){static Calendar c;return &c;}float GetCurrentGameTime(){return 12;}};
 enum class BSEventNotifyControl{kContinue};struct TESResetEvent{Actor*object;};template<class T>struct BSTEventSource{};}
struct RaceKey{int value=-1;RaceKey()=default;RaceKey(RE::Actor*a):value(a->race){}};
enum class Sex{Other};namespace Registry{Sex GetSex(RE::Actor*){return Sex::Other;}}
struct ActorEncounter{
 enum class EncounterType{Any,Victim,Aggressor,Submissive,Dominant};
 struct EncounterObj{RE::FormID id;RaceKey race;Sex sex;EncounterObj(RE::Actor*);};
 EncounterObj npc1,npc2;float _lastmet;uint8_t _timesmet,_timessubmissive,_timesdominant,_timesvictim,_timesaggressor;
 ActorEncounter(RE::Actor*,RE::Actor*,EncounterType);void Update(EncounterType);
};
struct StatisticsData{using EventResult=RE::BSEventNotifyControl;vector<uint32_t>removed;
 void DeleteStatistics(uint32_t id){removed.push_back(id);}
 EventResult ProcessEvent(const RE::TESResetEvent*,RE::BSTEventSource<RE::TESResetEvent>*);};
''' + function(stats, 'ActorEncounter::EncounterObj::EncounterObj(RE::Actor*') + function(stats, 'ActorEncounter::ActorEncounter(RE::Actor*') + function(stats, 'void ActorEncounter::Update(') + function(stats, 'StatisticsData::EventResult StatisticsData::ProcessEvent(const RE::TESResetEvent*') + r'''
int main(){RE::Actor a{14,0},b{15,0},nonActor{16,-1};
 alignas(ActorEncounter) unsigned char storage[sizeof(ActorEncounter)];memset(storage,0xCD,sizeof storage);
 auto*p=new(storage)ActorEncounter(&a,&b,ActorEncounter::EncounterType::Any);
 assert(p->npc1.race.value==0&&p->npc2.race.value==0);
 assert(p->_timesmet==1&&p->_timessubmissive==0&&p->_timesdominant==0&&p->_timesvictim==0&&p->_timesaggressor==0);
 p->~ActorEncounter();
 StatisticsData d;RE::TESResetEvent good{&a},other{&nonActor},empty{nullptr};
 d.ProcessEvent(&good,nullptr);d.ProcessEvent(&other,nullptr);d.ProcessEvent(&empty,nullptr);d.ProcessEvent(nullptr,nullptr);
 assert((d.removed==vector<uint32_t>{14}));
}
'''

failures = []
with tempfile.TemporaryDirectory(prefix='registry-contracts-') as tmp:
    for name, code in groups.items():
        source, binary = Path(tmp) / f'{name}.cpp', Path(tmp) / name
        source.write_text(code, encoding='utf-8')
        built = subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', str(source), '-o', str(binary)], capture_output=True, text=True)
        if built.returncode:
            print(name, built.stderr)
            failures.append(name + ': compile')
            continue
        run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
        if run.returncode:
            print(name, run.stderr)
            failures.append(name + ': assertion')
        else:
            print('PASS', name)
assert not failures, failures
