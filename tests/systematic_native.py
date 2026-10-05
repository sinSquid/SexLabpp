"""Audit call-chain regressions using extracted production functions and engine stand-ins."""
from pathlib import Path
import os
from source_regressions import ROOT, function, run
BASE = Path(os.environ.get('REVIEW_BASE_DIR', ROOT))
def source(path): return (BASE / path).read_text()

def creature_assignment():
    code = r'''
#include <algorithm>
#include <cassert>
#include <string>
#include <vector>
#include <numeric>
#include "Util/RequiredMatching.h"
namespace std { template<class... T> string format(const char* s,T&&...) { return s; } }
using StackID=int;
struct VM { int errors=0; void TraceStack(const char*,int){++errors;} };
namespace RE { using BSFixedString=std::string; struct Actor{int race;}; struct TESQuest{}; }
namespace Registry {
struct RaceKey {
 static constexpr int Human=0;
 int race; RaceKey(RE::Actor* a):race(a->race){};
 bool IsValid()const{return race>=0;} bool Is(int v)const{return race==v;}
 bool IsCompatibleWith(const RaceKey& actor)const{return race==actor.race || (race==3 && (actor.race==1 || actor.race==2));}
};
struct ActorFragment {static constexpr int MAX_ACTOR_COUNT=5;};
struct TagDetails {TagDetails(std::vector<std::string_view>){};};
struct Position {struct Data {int race; RaceKey GetRace()const {RE::Actor a{race};return RaceKey(&a);}} data;};
struct Scene {
 std::string id; std::vector<Position> positions;
 bool IsEnabled()const{return true;}bool IsPrivate()const{return false;}bool IsCompatibleTags(TagDetails&)const{return true;}
};
struct Library {
 std::vector<Scene> scenes; static Library* GetSingleton(){static Library l;return &l;}
 template<class F>void ForEachScene(F f){for(auto& s:scenes)if(f(&s))break;}
};
}
'''
    code += function(source('src/Papyrus/sslObject/sslCreatureAnimationSlots.cpp'), 'std::vector<RE::BSFixedString> GetByCreatureActorsTagsImpl(')
    code += r'''
int main(){
 auto* library=Registry::Library::GetSingleton(); VM vm;
 RE::Actor dog{1},wolf{2},human{0},invalid{-1};
 library->scenes={{"flexible",{{{3}},{{1}}}}, {"only-dog",{{{1}},{{1}}}}};
 auto find=[&](std::vector<RE::Actor*> actors){return GetByCreatureActorsTagsImpl(&vm,0,nullptr,2,actors,{});};
 assert(find({&dog,&wolf})==std::vector<std::string>{"flexible"});
 assert(find({&wolf,&dog})==std::vector<std::string>{"flexible"});
 assert(find({&dog,&dog}).size()==2);assert(find({&wolf,&wolf}).empty());
 assert(find({&dog,&human}).size()==2);assert(find({&invalid}).empty());
 assert(find({nullptr}).empty());
 // Exhaustive oracle: each nonhuman requires a distinct compatible position.
 for(int a=0;a<=3;++a)for(int b=0;b<=3;++b){
  library->scenes={{"scene",{{{a}},{{b}}}}};
  for(int x=0;x<=2;++x)for(int y=0;y<=2;++y){
   RE::Actor first{x},second{y};bool expected=false;
   auto fits=[](int slot,int actor){return actor==0 || slot==actor || (slot==3 && actor>0);};
   expected=(fits(a,x)&&fits(b,y)) || (fits(b,x)&&fits(a,y));
   assert(!find({&first,&second}).empty()==expected);
  }
 }
}
'''
    run('audit_creature_assignment', code)

def legacy_interactions():
    code = r'''
#include <cassert>
#include <memory>
#include <vector>
#include <cmath>
struct Vec {float x=0; float GetDistance(Vec v)const{return std::abs(x-v.x);}};
struct Node {struct {Vec translate;}world;};
namespace RE {struct Actor {
 bool graphExists=false,loaded=false;bool GetGraphVariableBool(const char*,bool& v){if(!graphExists)return false;v=loaded;return true;}
};}
namespace Settings {float fDistanceHand=10,fDistanceFoot=10,fAnimObjDist=10;}
struct Interaction {enum class Action{HandJob,FootJob,AnimObjFace};RE::Actor* partner;Action type;float distance;};
struct Position {RE::Actor* actor;struct {
 std::shared_ptr<Node> clitoris,hand_left,hand_right,foot_left,foot_right,animobj_a,animobj_b,animobj_r,animobj_l;
}nodes;};
struct Snapshot {
 Position position; std::vector<Interaction> interactions;
 const Vec* GetMouthStartPoint()const{static Vec mouth;return &mouth;}
 bool GetVaginaLimbInteractions(const Snapshot&);
 bool GetHeadAnimObjInteractions(const Snapshot&);
};
'''
    text = source('src/Thread/NiNode/Legacy/LegacyNiPosition.cpp')
    for name in ('GetVaginaLimbInteractions','GetHeadAnimObjInteractions'):
        code += function(text, 'bool NiPosition::Snapshot::'+name).replace('NiPosition::Snapshot::','Snapshot::')
    code += r'''
int main(){
 RE::Actor self,partner;Snapshot a{{&self,{}}},b{{&partner,{}}};
 a.position.nodes.hand_left=std::make_shared<Node>(); b.position.nodes.clitoris=std::make_shared<Node>();
 assert(a.GetVaginaLimbInteractions(b));assert(a.interactions.back().partner==&partner);
 b.position.nodes.animobj_a=std::make_shared<Node>();
 assert(!a.GetHeadAnimObjInteractions(b));partner.graphExists=true;assert(!a.GetHeadAnimObjInteractions(b));
 partner.loaded=true;assert(a.GetHeadAnimObjInteractions(b));
 b.position.nodes.animobj_a.reset();assert(!a.GetHeadAnimObjInteractions(b));
}
'''
    run('audit_legacy_interactions', code)

def finite_model():
    code = r'''
#include <array>
#include <cassert>
#include <cmath>
#include <limits>
#include <map>
#include <iostream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
namespace std {template<class... T>string format(const char* s,T&&... args){if constexpr(sizeof...(T)==2){std::array<std::string_view,2> parts{args...};return std::string(parts[0])+"_"+std::string(parts[1]);}return s;}}
namespace logger {template<class... T>void info(T&&...){}}
namespace Util {std::string CastLower(std::string s){return s;}}
namespace NiType {enum class Type{Kissing};enum class Cluster{Head};Cluster GetClusterForType(Type){return Cluster::Head;}std::array<Type,1>GetTypesForCluster(Cluster){return {Type::Kissing};}}
enum class Feature{Distance};
namespace magic_enum {
 template<class E>E unused();
 template<class E>std::string_view enum_name(E){return "Kissing";}
 template<class E>std::array<std::pair<E,std::string_view>,1>enum_entries(){return {{{E::Distance,"distance"}}};}
}
struct CSimpleIniA {
 std::map<std::string,double> values;std::string schema="legacy";
 double GetDoubleValue(const char*,const char* key,double fallback){auto i=values.find(key);return i==values.end()?fallback:i->second;}
 const char* GetValue(const char*,const char*,const char*){return schema.c_str();}
};
struct Descriptor {
 static constexpr auto Id=NiType::Type::Kissing;
 static inline float bias=0;static inline bool clusterModel=false;
 static inline std::array<std::array<float,1>,1>clusterCoefficients{};
 static inline std::array<float,1>coefficients{};
'''
    code += function(source('src/Thread/NiNode/NiDescriptor.h'), 'static void Initialize(')
    code += r'''
};
int main(){
 CSimpleIniA ini;ini.values={{"bias",0},{"distance",1},{"Kissing_distance",1}};
 for(auto schema:{"legacy","cluster-v2"}){
  ini.schema=schema;
  for(auto key:{"bias",schema==std::string_view("legacy")?"distance":"Kissing_distance"}){
   double saved=ini.values[key];
   for(double bad:{std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN(),1e100}){
    ini.values[key]=bad;bool rejected=false;try{Descriptor::Initialize(ini);}catch(const std::runtime_error&){rejected=true;}if(!rejected)std::cerr<<schema<<" "<<key<<" "<<bad<<"\n";assert(rejected);
   }
   ini.values[key]=saved;
  }
  Descriptor::Initialize(ini);
 }
}
'''
    run('audit_model_finite',code)


def kissing_missing_anchor():
    code=r'''
#include <array>
#include <cassert>
#include <cmath>
#include <memory>
#include <vector>
struct Vec{float x=0;float GetDistance(Vec v)const{return std::abs(x-v.x);}};
struct MotionDescriptor{float avgSpeed=0;Vec mean;Vec Mean()const{return mean;}};
struct NiMotion {
 enum Anchor{pMouth,vHeadY,vHeadX,vHeadZ};bool mouth=true;mutable int descriptions=0;
 bool HasSufficientData()const{return true;}bool HasMomentData(Anchor a)const{return a!=pMouth||mouth;}
 MotionDescriptor DescribeMotion(Anchor)const{++descriptions;return {};}
 Vec GetLatestMoment(Anchor)const{return {};}
};
namespace Settings {float fDistanceMouth=10,fMaxKissSpeed=10;}
namespace NiMath{float GetAngleCos(Vec,Vec){return 0;}}
namespace NiType{enum class Type{Kissing};}
struct INiDescriptor{enum class Feature{Angle01,Angle02,Angle03,Distance01,Velocity01};virtual ~INiDescriptor()=default;};
template<NiType::Type>struct NiDescriptor:INiDescriptor{void AddValue(Feature,float){}};
struct NiInteractionCluster{struct Interaction{std::unique_ptr<INiDescriptor> descriptor;float speed;};std::vector<Interaction>interactions;};
void AddBasicPairedScores01(INiDescriptor*,const MotionDescriptor&,const MotionDescriptor&){}
'''
    code+=function(source('src/Thread/NiNode/NiInteraction.cpp'),'NiInteractionCluster EvaluateKissingCluster(')
    code+=r'''
int main(){for(bool a:{false,true})for(bool b:{false,true}){
 NiMotion first{a},second{b};auto cluster=EvaluateKissingCluster(first,second);
 assert(cluster.interactions.size()==(a&&b?1:0));
 assert(first.descriptions==(a&&b?1:0));assert(second.descriptions==(a&&b?1:0));
}}
'''
    run('audit_kissing_missing',code)


def repeated_history():
    code=r'''
#include <cassert>
#include <string>
#include <vector>
namespace RE {using BSFixedString=std::string;struct TESQuest{};}
using StackID=int;
struct VM{void TraceStack(const char*,int){}};
struct Stage{};
struct Scene{Stage first,second;Stage*GetStageByID(const std::string& id){return id=="A"?&first:id=="B"?&second:nullptr;}};
struct Instance{Scene scene;Stage* active=&scene.first;int aligned=0,advanced=0;
 Scene*GetActiveScene(){return &scene;}Stage*GetActiveStage(){return active;}
 void RealignActors(){++aligned;}void AdvanceScene(Stage* s){active=s;++advanced;}
}storage;
#define QUESTARGS VM* a_vm,StackID a_stackID,RE::TESQuest*
#define GET_INSTANCE(ret) auto* instance=&storage
'''
    code+=function(source('src/Papyrus/sslThreadModel.cpp'),'std::vector<RE::BSFixedString> AdvanceScene(')
    code+=r'''
int main(){VM vm;
 auto history=AdvanceScene(&vm,0,nullptr,{"A","B"},"A");
 assert((history==std::vector<std::string>{"A","B","A"}));assert(storage.aligned==1 && storage.advanced==0);
 assert(AdvanceScene(&vm,0,nullptr,history,"unknown")==history);
 history=AdvanceScene(&vm,0,nullptr,history,"B");assert(history.size()==4&&storage.advanced==1);
 assert(AdvanceScene(&vm,0,nullptr,{},"A")==std::vector<std::string>{"A"});
}
'''
    run('audit_repeated_history',code)


def reordered_offsets():
    code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <memory>
#include <optional>
#include <vector>
namespace RE{struct Actor{};}
namespace Registry {
 enum class CoordinateType{X,Y,Z,R};struct Coordinate{struct{float x,y,z;}location;float rotation;};
 struct Offset{Coordinate coord;const Coordinate& GetOffset()const{return coord;}};
 struct Scene{Offset furnitureOffset;};struct Stage{struct Position{Offset offset;};std::vector<Position>positions;};
}
struct Instance {Registry::Scene scene;Registry::Stage stage;std::vector<RE::Actor*>actors;
 auto*GetActiveScene(){return &scene;}auto*GetActiveStage(){return &stage;}const auto&GetActors(){return actors;}
};
struct SceneHUD{std::shared_ptr<Instance>instance;auto GetThreadInstance(){return instance;}};
struct OffsetAdjustPanel{
 static constexpr float kDegreesPerRadian=57.2957795f;
 struct AxisState{float baseline=0,value=0;bool hasBaseline=false;};
 struct TargetItem{bool isCenter=false;RE::Actor*actor;size_t positionIndex;std::array<AxisState,4>axes{};std::optional<size_t>draggingAxis;};
 struct Definition{Registry::CoordinateType coordinate;};
 static constexpr std::array<Definition,4>kAxisDefinitions{{{Registry::CoordinateType::X},{Registry::CoordinateType::Y},{Registry::CoordinateType::Z},{Registry::CoordinateType::R}}};
 void RefreshValues(SceneHUD&,TargetItem&);
};
'''
    code+=function(source('src/Thread/Interface/Elements/OffsetAdjustPanel.cpp'),'void OffsetAdjustPanel::RefreshValues(')
    code+=r'''
int main(){
 RE::Actor a,b;SceneHUD hud{std::make_shared<Instance>()};hud.instance->actors={&a,&b};
 hud.instance->stage.positions={{{{{10,0,0},0}}},{{{{20,0,0},0}}}};
 OffsetAdjustPanel panel;OffsetAdjustPanel::TargetItem target{false,&a,0};
 panel.RefreshValues(hud,target);assert(target.axes[0].value==10 && target.axes[0].baseline==10);
 target.draggingAxis=0;hud.instance->actors={&b,&a};panel.RefreshValues(hud,target);
 assert(target.positionIndex==1);assert(!target.draggingAxis);assert(target.axes[0].value==20 && target.axes[0].baseline==20);
}
'''
    run('audit_reordered_offsets',code)
    # Registration holds the new scene/assignment; snapshots must be dropped first.
    text=source('src/Thread/Thread.cpp')
    for signature,mutation,following in [('bool Instance::SetActiveScene(','UnregisterNiInstance();','assignments = newAssignments;'),
                                       ('bool Instance::SetNextPermutation(','UnregisterNiInstance();','AdvanceScene(activeStage);')]:
        body=function(text,signature)
        assert body.index(mutation)<body.index('UnregisterNiInstanceLegacy();')<body.index(following)


def vector_rotation_units():
    code=r'''
#include <cassert>
#include <cmath>
#include <functional>
#include <numbers>
#include <string>
#include <vector>
namespace glm{float radians(float v){return v*std::numbers::pi_v<float>/180;}}
namespace RE{using BSFixedString=std::string;struct StaticFunctionTag{};}
using StackID=int;struct VM{int errors=0;void TraceStack(const char*,int){++errors;}};
namespace Registry {
 struct CoordinateType{static constexpr int Total=4;};
 struct Coordinate{float rotation=0;Coordinate()=default;Coordinate(const std::vector<float>& v):rotation(v[3]){}};
 struct Offset{Coordinate coordinate;void SetOffset(Coordinate v){coordinate=v;}};
 struct Stage{struct Position{Offset offset;};std::vector<Position>positions{2};};
 struct Scene{Offset furnitureOffset;std::vector<Stage>stages{2};Stage*GetStageByID(std::string id){return id=="valid"?&stages[0]:nullptr;}
  template<class F>void ForEachStage(F visitor){for(auto& stage:stages)if(visitor(&stage))break;}
 };
 struct Library{Scene scene;static Library*GetSingleton(){static Library l;return &l;}
 template<class F>bool EditScene(std::string id,F visitor){if(id!="scene")return false;visitor(&scene);return true;}
 };
}
#define STATICARGS VM* a_vm,StackID a_stackID,RE::StaticFunctionTag*
#define POSITION(ret) if(n<0||n>=2)return ret
'''
    for signature in ('void SetSceneOffsetA(', 'void SetStageOffsetA('):
        code+=function(source('src/Papyrus/SexLabRegistry.cpp'),signature)
    code+=r'''
int main(){VM vm;auto*library=Registry::Library::GetSingleton();float pi=std::numbers::pi_v<float>;
 for(float degrees:{0.f,90.f,180.f,-90.f,360.f}){
  SetSceneOffsetA(&vm,0,nullptr,"scene",{1,2,3,degrees});assert(std::abs(library->scene.furnitureOffset.coordinate.rotation-glm::radians(degrees))<1e-6);
  SetStageOffsetA(&vm,0,nullptr,"scene","",1,{1,2,3,degrees});
  for(auto& stage:library->scene.stages)assert(std::abs(stage.positions[1].offset.coordinate.rotation-glm::radians(degrees))<1e-6);
 }
 SetStageOffsetA(&vm,0,nullptr,"scene","valid",0,{1,2,3,180});assert(std::abs(library->scene.stages[0].positions[0].offset.coordinate.rotation-pi)<1e-6);
 SetSceneOffsetA(&vm,0,nullptr,"scene",{});SetStageOffsetA(&vm,0,nullptr,"scene","valid",0,{});assert(vm.errors==2);
}
'''
    run('audit_vector_rotation',code)


if __name__=='__main__':
    creature_assignment(); legacy_interactions(); finite_model(); kissing_missing_anchor(); repeated_history(); reordered_offsets(); vector_rotation_units()
    print('PASS: 7 native audit groups (production functions, engine stand-ins; snapshot invalidation source contracts)')
