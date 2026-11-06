"""Compile extracted production helpers/callbacks with bounded engine stand-ins.

Covers T5/T6/T7/T8 and serialization record-version dispatch. No game-runtime,
thread scheduler, UI rendering, or legacy binary-layout emulation is claimed.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(path, signature):
    source = (ROOT / path).read_text(encoding='utf-8')
    baseline = {
        'T5': 'void SceneSelectPanel::OnAnnotationSave(',
        'T6': 'Segment ClosestSegmentBetweenSegments(',
        'T7': 'void StageSelectMenu::RefreshSceneGraphView(',
        'T8': 'void StageSelectMenu::RenderSceneGraphView()',
    }.get(os.environ.get('THREAD_REVIEW_BASELINE'))
    if signature == baseline:
        source = subprocess.check_output(['git', 'show', '10d56c9a:' + path], cwd=ROOT, text=True)
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cctype>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <vector>
using namespace std::literals;
namespace RE {
using BSFixedString = std::string;
using VMHandle = unsigned long long;
struct TESQuest {};
struct NiPoint3 {
 float x=0,y=0,z=0;
 NiPoint3 operator+(NiPoint3 b) const { return {x+b.x,y+b.y,z+b.z}; }
 NiPoint3 operator-(NiPoint3 b) const { return {x-b.x,y-b.y,z-b.z}; }
 NiPoint3 operator*(float f) const { return {x*f,y*f,z*f}; }
 bool operator==(const NiPoint3&) const = default;
 float Dot(NiPoint3 b) const { return x*b.x+y*b.y+z*b.z; }
 float SqrLength() const { return Dot(*this); }
}; }
struct Segment {
 RE::NiPoint3 start, end;
 bool IsPoint() const { return start==end; }
 RE::NiPoint3 Vector() const { return end-start; }
};
'''
code += function('src/Thread/Interaction/NiSurface/GeometryMath.cpp', 'Segment ClosestSegmentBetweenSegments(')
code += r'''
namespace Registry {
struct Stage {};
struct Tags {
 std::vector<std::string> annotations;
 const std::vector<std::string>& GetAnnotations() const { return annotations; }
 void RemoveAnnotation(const std::string& a) {
  auto it=std::find(annotations.begin(),annotations.end(),a);
  if(it!=annotations.end()) annotations.erase(it);
 }
 void AddAnnotation(const std::string& a) { annotations.push_back(a); }
};
struct Scene { Tags tags; };
struct Library {
 Scene scene;
 static Library* GetSingleton() { static Library lib; return &lib; }
 const Scene* GetSceneById(const std::string&) { return &scene; }
 template<class F> void EditScene(const std::string&,F f) { f(&scene); }
}; }
struct SceneSelectPanel {
 struct SceneEntry { std::string id,annotations; char annotBuf[256]{}; };
 void OnAnnotationSave(SceneEntry&);
};
'''
code += function('src/Thread/Interface/Elements/SceneSelectPanel.cpp', 'void SceneSelectPanel::OnAnnotationSave(')
code += r'''
struct Instance {
 Registry::Scene* scene=nullptr;
 Registry::Stage* stage=nullptr;
 RE::TESQuest* linkedQst=nullptr;
 void OnStageChangedUpdateHUD();
 static inline std::map<RE::TESQuest*,Instance*> instances;
 static Instance* GetInstance(RE::TESQuest* q) { auto i=instances.find(q);return i==instances.end()?nullptr:i->second; }
 Registry::Scene* GetActiveScene(){return scene;}
 Registry::Stage* GetActiveStage(){return stage;}
};
struct StageSelectMenu {
 static StageSelectMenu& GetSingleton(){static StageSelectMenu m;return m;}
 struct GraphNode { const Registry::Stage* stage; };
 RE::TESQuest* _linkedThread=nullptr;
 bool _choicePending=false,_graphOpen=false,blocked=false,visible=false;
 std::vector<int> _choices;
 std::vector<float> _choiceScrollOffsets;
 const Registry::Stage* _choiceOrigin=nullptr;
 const Registry::Scene* _graphScene=nullptr;
 std::vector<GraphNode> _graphNodes;
 int _graphCurrentIndex=-1,builds=0,cancels=0,renders=0;
 void ClosePendingChoice(){_choicePending=false;++cancels;}
 void BuildSceneGraph(Instance& i){_graphScene=i.scene;++builds;}
 void SetBlocksInput(bool b){blocked=b;}
 void Hide(){visible=false;}
 void Close();
 void RefreshSceneGraphView(RE::TESQuest*);
 void RenderSceneGraphView();
};
'''
code += function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::Close()')
code += function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::RefreshSceneGraphView(')
code += r'''
namespace Interface {
using StageSelectMenu = ::StageSelectMenu;
struct SceneHUD {
 RE::TESQuest* owner=nullptr;int offsets=0;
 static SceneHUD& GetSingleton(){static SceneHUD h;return h;}
 SceneHUD* GetForThread(RE::TESQuest* q){return q&&q==owner?this:nullptr;}
 void RefreshStageOffsets(){++offsets;}
};
}
'''
code += function('src/Thread/Thread.cpp', 'void Instance::OnStageChangedUpdateHUD()')
render = function('src/Thread/Interface/StageSelectMenu.cpp', 'void StageSelectMenu::RenderSceneGraphView()')
# Execute the lifetime gate before entering ImGui; drawing remains engine-owned.
code += render[:render.index('auto& scale')] + '++renders;\n}\n'
assert render.index('if (!inst)') < render.index('ImGuiMCP::Begin(')
assert render.count('Instance::GetInstance(_linkedThread)') == 1

code += r'''
namespace SKSE {
struct SerializationInterface {
 std::vector<std::pair<uint32_t,uint32_t>> records;
 size_t cursor=0;
 bool OpenRecord(uint32_t type,uint32_t version){records.emplace_back(type,version);return true;}
 bool GetNextRecordInfo(uint32_t& t,uint32_t& v,uint32_t& len){
  if(cursor==records.size()) return false;
  t=records[cursor].first;v=records[cursor++].second;len=0;return true;
 }
}; }
template<class T> struct Singleton { static T* GetSingleton(){static T t;return &t;} };
namespace logger { template<class...T> void info(T&&...){} template<class...T> void warn(T&&...){} template<class...T> void error(T&&...){} }
namespace Registry::Statistics {
struct StatisticsData : Singleton<StatisticsData> {
 int saves=0;std::vector<uint32_t> loaded;
 void Save(SKSE::SerializationInterface*){++saves;}
 void Load(SKSE::SerializationInterface*,uint32_t v,uint32_t length){assert(length==0);loaded.push_back(v);}
 void Revert(SKSE::SerializationInterface*){}
}; }
namespace Papyrus { struct Tracking : Singleton<Tracking> {
 int saves=0,loads=0;
 void Save(SKSE::SerializationInterface*){++saves;}
 void Load(SKSE::SerializationInterface*){++loads;}
 void Revert(SKSE::SerializationInterface*){}
}; }
namespace Thread::Collision { struct CollisionHandler { static void Clear(){} }; }
'''
header = (ROOT / 'src/Serialization.h').read_text(encoding='utf-8')
code += '\n'.join(line for line in header.splitlines() if not line.startswith(('#include', '#pragma once')))
code += r'''
double distanceSq(Segment s){return (s.start-s.end).SqrLength();}
double pointToSegment(RE::NiPoint3 p,Segment s){
 auto d=s.Vector();double a=d.SqrLength();
 double t=a>0?std::clamp(double((p-s.start).Dot(d))/a,0.,1.):0.;
 return (p-(s.start+d*float(t))).SqrLength();
}
double reference(Segment l,Segment r){
 double best=std::min({pointToSegment(l.start,r),pointToSegment(l.end,r),pointToSegment(r.start,l),pointToSegment(r.end,l)});
 auto d=l.Vector(),e=r.Vector(),w=l.start-r.start;
 double a=d.Dot(d),b=d.Dot(e),c=e.Dot(e),f=d.Dot(w),g=e.Dot(w),det=a*c-b*b;
 if(det>1e-12){
  double s=(b*g-c*f)/det,t=(a*g-b*f)/det;
  if(s>=0&&s<=1&&t>=0&&t<=1) best=std::min(best,double(((l.start+d*float(s))-(r.start+e*float(t))).SqrLength()));
 }
 return best;
}
int main(){
 auto check=[](Segment a,Segment b,double expected){
  auto out=ClosestSegmentBetweenSegments(a,b);
  assert(std::abs(std::sqrt(distanceSq(out))-expected)<1e-5);
  auto reverse=ClosestSegmentBetweenSegments(b,a);
  assert(std::abs(distanceSq(out)-distanceSq(reverse))<1e-4);
 };
 check({{0,0,0},{1,0,0}},{{.5f,-1,0},{.5f,1,0}},0);
 check({{0,0,0},{1,0,0}},{{.5f,-1,2},{.5f,1,2}},2);
 check({{0,0,0},{1,0,0}},{{2,-1,0},{2,1,0}},1);
 check({{0,0,0},{1,0,0}},{{2,0,0},{3,0,0}},1);
 check({{0,0,0},{3,0,0}},{{2,0,0},{4,0,0}},0);
 check({{0,0,0},{3,0,0}},{{4,1,0},{2,1,0}},1);
 check({{0,0,0},{0,0,0}},{{0,0,2},{0,0,2}},2);
 check({{.5f,2,0},{.5f,2,0}},{{0,0,0},{1,0,0}},2);
 std::mt19937 rng(47011);std::uniform_real_distribution<float> coord(-10,10);
 auto p=[&]{return RE::NiPoint3{coord(rng),coord(rng),coord(rng)};};
 for(int i=0;i<10000;++i){
  Segment a{p(),p()},b{p(),p()};
  double got=distanceSq(ClosestSegmentBetweenSegments(a,b)),want=reference(a,b);
  assert(std::abs(got-want)<1e-3);
 }
 SceneSelectPanel panel;SceneSelectPanel::SceneEntry entry;
 auto& tags=Registry::Library::GetSingleton()->scene.tags;
 tags.annotations={"first","second","third"};entry.annotations="first,second,third";
 std::snprintf(entry.annotBuf,sizeof(entry.annotBuf)," new-a, new-b ");
 panel.OnAnnotationSave(entry);assert((tags.annotations==std::vector<std::string>{"new-a","new-b"}));
 entry.annotBuf[0]='\0';panel.OnAnnotationSave(entry);assert(tags.annotations.empty());
 RE::TESQuest q,other;Registry::Scene a,b;Registry::Stage s,t;
 Instance ia{&a,&s},ib{&b,&t};Instance::instances={{&q,&ia},{&other,&ib}};
 StageSelectMenu menu;menu._linkedThread=&q;menu._graphOpen=true;menu._graphScene=&a;
 menu._choicePending=true;menu._choiceOrigin=&s;menu._graphNodes={{&s},{&t}};
 menu.RefreshSceneGraphView(&other);assert(menu.builds==0&&menu.cancels==0&&menu._graphScene==&a);
 menu.RefreshSceneGraphView(&q);assert(menu._graphCurrentIndex==0&&menu.cancels==0);
 ia.stage=&t;menu.RefreshSceneGraphView(&q);assert(menu.cancels==1&&menu._graphCurrentIndex==1);
 // Open a choice while HUD exists, then hide HUD and change stage by script.
 auto& pendingMenu=StageSelectMenu::GetSingleton();auto& hud=Interface::SceneHUD::GetSingleton();
 pendingMenu._linkedThread=&q;pendingMenu._choicePending=true;pendingMenu._choiceOrigin=&s;
 hud.owner=&q;ia.linkedQst=&q;ib.linkedQst=&other;ia.stage=&s;
 ib.OnStageChangedUpdateHUD();assert(pendingMenu._choicePending&&hud.offsets==0);
 hud.owner=nullptr;ia.stage=&t;ia.OnStageChangedUpdateHUD();
 assert(!pendingMenu._choicePending&&pendingMenu.cancels==1&&hud.offsets==0);
 hud.owner=&q;ia.OnStageChangedUpdateHUD();assert(hud.offsets==1);
 menu.RenderSceneGraphView();assert(menu.renders==1);
 menu.blocked=menu.visible=true;Instance::instances.erase(&q);
 menu.RenderSceneGraphView();assert(menu.renders==1&&!menu.visible&&!menu.blocked&&!menu._graphOpen);
 SKSE::SerializationInterface out;Serialization::Serialize::SaveCallback(&out);
 assert(out.records.size()==2&&out.records[0].second==2&&out.records[1].second==1);
 SKSE::SerializationInterface in;
 using S=Serialization::Serialize;
 in.records={{S::_Statistics,1},{S::_Statistics,2},{S::_Statistics,3},{S::_Tracking,1},{S::_Tracking,2}};
 S::LoadCallback(&in);
 assert((Registry::Statistics::StatisticsData::GetSingleton()->loaded==std::vector<uint32_t>{1,2}));
 assert(Papyrus::Tracking::GetSingleton()->loads==1);
}
'''

with tempfile.TemporaryDirectory(prefix='thread-review-') as directory:
    source, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
    source.write_text(code, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-D_GLIBCXX_DEBUG', '-Wno-multichar', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: T5 annotation replacement, T6 closest segments (8 cases + 10000 independent-reference samples), T7 graph ownership, T8 missing-instance gate, statistics/tracking version dispatch.')
