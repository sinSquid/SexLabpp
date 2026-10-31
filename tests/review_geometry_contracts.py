"""Small native contract probes using actual production function bodies.

Source-body contract regressions. Does not load Skyrim or modify source.
Requires the same CXX (default g++) as the repository's existing native tests.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def read_source(path):
    if base := os.environ.get("REVIEW_BASE"):
        return subprocess.check_output(["git", "show", f"{base}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


def function(source, signature):
    start = source.index(signature)
    brace = source.index("{", start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def sex_fixture():
    source = read_source("src/Thread/Interaction/NiSurface/CollisionManager.cpp")
    code = r'''
#include <cassert>
#include <cstddef>
#include <vector>
namespace RE { struct Actor { int actualSex=1; }; }
namespace Registry {
enum class Sex { Male=1, Female=2, Futa=4 };
Sex GetSex(RE::Actor* actor){return Sex(actor->actualSex);}
struct Mask { int value; bool any(Sex v)const{return (value&int(v))!=0;} Sex get()const{return Sex(value);} };
struct Data { Mask GetSex()const{return {3};} };
struct Position { Data data; };
struct Scene { Position pos; const Position* GetNthPosition(std::size_t)const{return &pos;} };
}
int shaftCalls=0,vaginalCalls=0;
struct ActorState {
 RE::Actor* actor; Registry::Mask sex;
 struct Geometry {std::vector<int> shafts{1};} geometry;
 ActorState(RE::Actor* a,Registry::Sex s):actor(a),sex{int(s)}{}
 struct Frame {
  ActorState& state;
  bool operator==(const Frame& rhs)const{return state.actor==rhs.state.actor;}
  bool DetectShaftHead(const Frame&,int){++shaftCalls;return true;}
  bool DetectShaftHand(const Frame&,int){return false;}
  bool DetectShaftCrotch(const Frame&,int){return false;}
  bool DetectShaftFoot(const Frame&,int){return false;}
  bool DetectVaginalContact(const Frame&){++vaginalCalls;return true;}
  bool DetectVaginalOral(const Frame&){++vaginalCalls;return true;}
  bool DetectVaginalLimb(const Frame&){++vaginalCalls;return true;}
 };
};
struct Scene {
 std::vector<ActorState> positions;
 Scene(const std::vector<RE::Actor*>&,const Registry::Scene*);
 void DetectShaftInteractions(std::vector<ActorState::Frame>&,const ActorState::Frame&);
 void DetectVaginalInteractions(std::vector<ActorState::Frame>&,const ActorState::Frame&);
};
'''
    code += function(source, "Scene::Scene(")
    code += function(source, "void Scene::DetectShaftInteractions(")
    code += function(source, "void Scene::DetectVaginalInteractions(")
    code += r'''
int main(){
 for(int actualSex:{1,2,4}){
  RE::Actor actor{actualSex}; Registry::Scene profile; Scene scene({&actor},&profile);
  std::vector<ActorState::Frame> frames{{scene.positions.front()}};
  shaftCalls=vaginalCalls=0;
  scene.DetectShaftInteractions(frames,frames.front());
  scene.DetectVaginalInteractions(frames,frames.front());
  assert((shaftCalls>0)==(actualSex!=2));
  assert((vaginalCalls>0)==(actualSex!=1));
 }
}
'''
    return code


VEC = r'''
#include <algorithm>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <tuple>
struct Vec {
 float x{},y{},z{};
 Vec operator+(Vec v)const{return {x+v.x,y+v.y,z+v.z};}
 Vec operator-(Vec v)const{return {x-v.x,y-v.y,z-v.z};}
 Vec operator-()const{return {-x,-y,-z};}
 Vec operator*(float s)const{return {x*s,y*s,z*s};}
 bool operator==(const Vec&)const=default;
 float Dot(Vec v)const{return x*v.x+y*v.y+z*v.z;}
 float SqrLength()const{return Dot(*this);}
 float Length()const{return std::sqrt(SqrLength());}
 float GetDistance(Vec v)const{return (*this-v).Length();}
};
namespace RE {using NiPoint3=Vec; float rad_to_deg(float v){return v*180.f/3.14159265358979323846f;}}
namespace Settings {constexpr float fAngleToHeadTolerance=20, fAngleToHeadSidewaysTolerance=50, fAngleToHeadFrontalTolerance=45;}
'''


def angle_fixture():
    math = read_source("src/Thread/Interaction/NiSurface/GeometryMath.cpp")
    state = read_source("src/Thread/Interaction/NiSurface/ActorState.cpp")
    start = state.index("const auto [angleToHead, angleToMouth, angleToBase]")
    end = state.index("const auto penetratingSkull", start)
    body = state[start:end]
    code = VEC + "namespace GeometryMath {\n"
    code += function(math, "float GetAngleDegree(")
    code += function(math, "RE::NiPoint3 ProjectedComponent(") + "}\n"
    code += r'''
struct Segment {Vec start,end;Vec Vector()const{return end-start;}};
struct Partner {Segment GetCrotchSegment()const{return {{},{0,1,0}};}};
std::pair<bool,bool> classify(Vec base){
 const Vec vHead{0,1,0}; const struct{Vec translate;} headWorld{};
 const Partner partnerGeometry;
 const Segment shaftSegment{base,{0,0,0}};
'''
    code += body
    code += r'''
 (void)aimingAtHead;return {atSideOfHead,inFrontOfHead};
}
int main(){
 assert((classify({10,0,0})==std::pair{true,false}));
 assert((classify({10,0.01f,0})==std::pair{true,false}));
 assert((classify({0,10,0})==std::pair{false,true}));
 assert((classify({0,-10,0})==std::pair{false,false}));
}
'''
    return code


def lock_fixture(shaft, replace_buffer=False):
    source = read_source("src/Thread/Interaction/NiSurface/SurfaceCache.cpp")
    name = "ReadShaftCandidateLocalPositions" if shaft else "ReadCandidateLocalPositions"
    original = function(source, "bool " + name + "(")
    # Keep the real dynamic-buffer branch verbatim; the static fallback is irrelevant here.
    prefix = original[:original.index("            auto& partition = a_partition->partitions[0];")]
    code = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <vector>
namespace DirectX {
struct XMVECTOR {float x,y,z;};struct XMFLOAT3 {float x,y,z;};
int reads=0;
bool locked=false;const XMVECTOR* expected=nullptr;
void XMStoreFloat3(XMFLOAT3* out,const XMVECTOR& value){assert(locked && &value==expected);++reads;*out={value.x,value.y,value.z};}
}
namespace RE {
struct NiPoint3 {float x,y,z;}; struct NiSkinPartition {};
struct BSGeometry {virtual ~BSGeometry()=default;};
struct BSDynamicTriShape:BSGeometry {
 struct Runtime {void* dynamicData=nullptr;int lock=0;std::uint32_t dataSize=16;} runtime;
 Runtime& GetDynamicTrishapeRuntimeData(){return runtime;}
};
std::function<void()> beforeAcquire;
struct BSSpinLockGuard {
 explicit BSSpinLockGuard(int&){if(beforeAcquire)beforeAcquire();DirectX::locked=true;}
 ~BSSpinLockGuard(){DirectX::locked=false;}
};
}
template<class T,class U>T netimmerse_cast(U* value){return dynamic_cast<T>(value);}
struct Candidate {std::uint16_t vertex;float weight;RE::NiPoint3 local;};
struct ShaftCandidate {std::uint16_t vertex;float chainWeight;RE::NiPoint3 local;};
'''
    code += prefix + "            (void)a_partition; return false;\n        }\n"
    code += r'''
int main(){
 RE::BSDynamicTriShape geometry;RE::NiSkinPartition partition;
 DirectX::XMVECTOR vertex{1,2,3};geometry.runtime.dynamicData=&vertex;
 // Deterministically emulate a buffer owner clearing the pointer before our lock succeeds.
 RE::beforeAcquire=[&]{geometry.runtime.dynamicData=nullptr;geometry.runtime.dataSize=0;};
'''
    if replace_buffer:
        code += "DirectX::XMVECTOR replacement[2]{{7,8,9},{4,5,6}};RE::beforeAcquire=[&]{geometry.runtime.dynamicData=replacement;geometry.runtime.dataSize=32;DirectX::expected=replacement;};\n"
    if shaft:
        code += "std::vector<ShaftCandidate> candidates{{0,1,{}}};\n"
    else:
        code += "std::array<std::vector<Candidate>,2> candidates{{{{0,1,{}}},{{0,1,{}}}}};\n"
    if replace_buffer:
        code += f"assert({name}(&geometry,&partition,candidates));\nassert(geometry.runtime.dataSize==32);\n"
        code += "assert(candidates[0].local.x==7);\n" if shaft else "assert(candidates[0][0].local.x==7&&candidates[1][0].local.x==7);\n"
    else:
        code += f"assert(!{name}(&geometry,&partition,candidates));\nassert(DirectX::reads==0);\n"
    code += "}\n"
    return code


def opening_refresh_fixture():
    source = read_source("src/Thread/Interaction/NiSurface/ActorGeometry.cpp")
    code = r'''
#include <cassert>
#include <cstdint>
#include <optional>
namespace RE {struct NiAVObject {};struct Actor {NiAVObject root;NiAVObject* Get3D(){return &root;}};}
std::uint64_t signature=1;std::uint64_t GetBipedSignature(RE::Actor*){return signature;}
constexpr int SHAFT_EQUIPMENT_STABLE_FRAMES=2;
struct Opening {bool attached=true;bool IsAttachedTo(RE::NiAVObject*)const{return attached;}};
struct ActorGeometry {
 RE::Actor* ownerActor;std::uint64_t openingEquipmentSignature=1;int stableOpeningFrames=0;
 bool openingSearchPending=false;std::optional<Opening> trackedVagina{Opening{}},trackedAnus{Opening{}};
 int scans=0;bool available=true;
 void DiscoverOpenings(){++scans;if(available){trackedVagina.emplace();trackedAnus.emplace();}}
 void RefreshOpenings();
};
'''
    code += function(source, "void ActorGeometry::RefreshOpenings()")
    code += r'''
int main(){
 RE::Actor actor;ActorGeometry geometry;geometry.ownerActor=&actor;
 for(int i=0;i<10;++i)geometry.RefreshOpenings();assert(geometry.scans==0);
 signature=2;geometry.RefreshOpenings();assert(!geometry.trackedVagina&&geometry.scans==0);
 signature=3;geometry.RefreshOpenings();assert(geometry.scans==0); // another change restarts settling
 geometry.RefreshOpenings();assert(geometry.scans==1&&geometry.trackedVagina);
 for(int i=0;i<10;++i)geometry.RefreshOpenings();assert(geometry.scans==1);
 geometry.trackedVagina->attached=false;geometry.RefreshOpenings();assert(!geometry.trackedVagina);
 geometry.RefreshOpenings();assert(geometry.scans==2&&geometry.trackedVagina);
 signature=4;geometry.available=false;geometry.RefreshOpenings();geometry.RefreshOpenings();assert(geometry.scans==3);
 for(int i=0;i<20;++i)geometry.RefreshOpenings();assert(geometry.scans==3); // no full-frame retry loop
 signature=5;geometry.available=true;geometry.RefreshOpenings();geometry.RefreshOpenings();assert(geometry.scans==4&&geometry.trackedVagina);
}
'''
    return code


def grinding_fixture():
    state_source = read_source("src/Thread/Interaction/NiSurface/ActorState.cpp")
    header = read_source("src/Thread/Interaction/NiSurface/GeometryMath.h")
    math = read_source("src/Thread/Interaction/NiSurface/GeometryMath.cpp")
    detect = function(state_source, "bool ActorState::Frame::DetectShaftCrotch(")
    marker = "        } else {\n            const auto crotchSegment = state.geometry.GetCrotchSegment();"
    body = detect[detect.index(marker) + len("        } else {"):]
    code = VEC + "#include <vector>\nnamespace GeometryMath {\n"
    code += function(header, "struct Segment") + ";\n"
    code += function(math, "Segment ClosestSegmentBetweenSegments(")
    code += function(math, "float GetAngleDegree(") + "}\n"
    code += r'''
namespace Settings {constexpr float fDistanceCrotch=2,fAnglePenetration=40,fAngleGrinding=70,fAdjustSchlongVaginalLimit=90;}
namespace Interaction {enum class Action{Anal,Grinding};}
struct Geometry {GeometryMath::Segment GetCrotchSegment()const{return {{0,1,0},{0,2,0}};}};
struct State {Geometry geometry;int actor=1;};State state;
struct Partner {State state;};Partner a_partner;
struct Results {std::vector<Interaction::Action> values;void emplace_back(int,Interaction::Action action,float,Vec){values.push_back(action);}} interactions;
GeometryMath::Segment shaftSegment{{0,0,0},{1,0,0}};
bool RotateNode(int*,const GeometryMath::Segment&,Vec,float){return true;}
bool detectFallback(){const auto shaftTip=shaftSegment.end;int* shaftNode=nullptr;{
'''
    code += body
    code += r'''
int main(){
 assert(detectFallback());assert(interactions.values.back()==Interaction::Action::Grinding);
 shaftSegment={{0,0,0},{0,2,0}};
 assert(detectFallback());assert(interactions.values.back()==Interaction::Action::Anal);
}
'''
    return code


def revert_fixture():
    source = read_source("src/Thread/Interaction/NiSurface/CollisionManager.cpp")
    update = function(source, "void Scene::UpdateInteractions(")
    prefix = update[:update.index("        bool geometryChanged")]
    code = r'''
#include <cassert>
#include <atomic>
#include <chrono>
#include <functional>
#include <future>
#include <memory>
#include <mutex>
#include <thread>
#include <utility>
#include <vector>
struct ActorState {};
struct Scene {
 std::mutex _mutex;bool valid=true;int samples=0;std::vector<ActorState> positions{{}};
 void UpdateInteractions(float,bool);
 bool VisitPositions(const std::function<bool(const ActorState&)>&)const;
};
struct Manager {
 static inline std::mutex _mutex,_geometryMutex;
 static inline std::vector<std::pair<unsigned,std::shared_ptr<Scene>>> scenes;
 static void Clear();
};
'''
    # Const query methods use the same mutable mutex as production.
    code = code.replace("std::mutex _mutex;bool valid", "mutable std::mutex _mutex;bool valid")
    code += prefix + "        (void)a_delta;(void)a_drawCollision;++samples;\n}\n"
    code += function(source, "bool Scene::VisitPositions(")
    code += function(source, "void Manager::Clear()")
    code += r'''
int main(){
 auto oldScene=std::make_shared<Scene>();Manager::scenes.emplace_back(1,oldScene);
 auto oldSnapshot=Manager::scenes;
 oldSnapshot.front().second->UpdateInteractions(0.01f,false);assert(oldScene->samples==1);
 std::unique_lock geometryLock(Manager::_geometryMutex);
 std::atomic<bool> entered=false;
 auto clear=std::async(std::launch::async,[&]{entered=true;Manager::Clear();});
 while(!entered.load())std::this_thread::yield();
 assert(clear.wait_for(std::chrono::milliseconds(20))==std::future_status::timeout);
 geometryLock.unlock();clear.get();assert(Manager::scenes.empty());
 oldSnapshot.front().second->UpdateInteractions(0.01f,false);assert(oldScene->samples==1);
 int visits=0;oldScene->VisitPositions([&](const auto&){++visits;return false;});assert(visits==0);
 auto nextScene=std::make_shared<Scene>();Manager::scenes.emplace_back(2,nextScene);
 nextScene->UpdateInteractions(0.01f,false);assert(nextScene->samples==1);
 Manager::Clear();nextScene->UpdateInteractions(0.01f,false);assert(nextScene->samples==1);
}
'''
    return code


def detached_fixture():
    shaft = read_source("src/Thread/Interaction/NiSurface/Shaft.cpp")
    cache = read_source("src/Thread/Interaction/NiSurface/SurfaceCache.cpp")
    original = function(shaft, "void Shaft::UpdateCollisionShape()")
    prefix = original[:original.index("        if (!surface) {")]
    code = r'''
#include <cassert>
#include <cstdint>
#include <memory>
#include <optional>
namespace RE {
struct NiAVObject {NiAVObject* parent=nullptr;};
struct Skin {};
struct BSGeometry:NiAVObject {
 struct {std::shared_ptr<Skin> skinInstance;} runtime;
 auto& GetGeometryRuntimeData(){return runtime;}
};
struct Actor {NiAVObject* root;NiAVObject* Get3D(){return root;}};
}
std::uint64_t GetBipedSignature(RE::Actor*){return 1;}
'''
    if "bool IsAttachedTo(" in cache:
        code += function(cache, "bool IsAttachedTo(")
    code += r'''
struct Shaft {
 struct Surface {std::shared_ptr<RE::BSGeometry> geometry;RE::Skin* skinInstance;};
 std::optional<Surface> surface;std::optional<int> collisionShape{1};RE::Actor* ownerActor;
 std::uint64_t equipmentSignature=0;int stableEquipmentFrames=0;bool surfaceSearchPending=false;
 void UpdateCollisionShape();
};
'''
    code += prefix + "}\n"
    code += r'''
int main(){
 RE::NiAVObject currentRoot,oldDetachedPart;RE::Actor actor{&currentRoot};
 auto mesh=std::make_shared<RE::BSGeometry>();mesh->parent=&oldDetachedPart;
 mesh->runtime.skinInstance=std::make_shared<RE::Skin>();
 Shaft value;value.ownerActor=&actor;value.surface=Shaft::Surface{mesh,mesh->runtime.skinInstance.get()};
 value.UpdateCollisionShape();assert(!value.surface&&value.surfaceSearchPending&&!value.collisionShape);
}
'''
    return code


def bone_fixture(opening):
    source = read_source("src/Thread/Interaction/NiSurface/SurfaceCache.cpp" if opening else "src/Thread/Interaction/NiSurface/Shaft.cpp")
    begin = source.index("        for (auto& bone : bones)" if opening else "        for (auto& bone : surface->bones)")
    end = source.index("            bone.transform =", begin)
    branch = source[begin:end]
    code = r'''
#include <cassert>
#include <memory>
#include <optional>
#include <vector>
struct Node {};
struct SkinData {unsigned GetBoneCount()const{return 1;}};
struct Skin {unsigned numMatrices=1;Node* bones[1];};
struct Bone {unsigned skinIndex=0;std::shared_ptr<Node> node;};
'''
    if opening:
        code += r'''
struct OpeningShape {};
struct TrackedOpening {
 Skin* skinInstance;SkinData data;std::vector<Bone> bones;int refreshed=0;
 bool RefreshBinding(){++refreshed;return true;}
 std::optional<OpeningShape> Check(){auto* skinData=&data;
'''
        code += branch + "        }\nreturn OpeningShape{};}\n};\n"
        code += "int main(){Node replacement;Skin skin{1,{&replacement}};TrackedOpening value;value.skinInstance=&skin;value.bones.push_back({0,std::make_shared<Node>()});assert(!value.Check());assert(value.refreshed==1);}\n"
    else:
        code += r'''
struct Shaft {
 struct Surface {Skin* skinInstance;std::vector<Bone> bones;};
 std::optional<Surface> surface;std::optional<int> collisionShape{1};SkinData data;
 bool surfaceSearchPending=false;int stableEquipmentFrames=99;
 void Check(){auto* skinData=&data;
'''
        code += branch + "        }\n}\n};\n"
        code += "int main(){Node replacement;Skin skin{1,{&replacement}};Shaft value;value.surface=Shaft::Surface{&skin,{{0,std::make_shared<Node>()}}};value.Check();assert(!value.surface&&!value.collisionShape&&value.surfaceSearchPending&&value.stableEquipmentFrames==0);}\n"
    return code


if __name__ == "__main__":
    failures = []
    with tempfile.TemporaryDirectory(prefix="sexlab-geometry-review-") as tmp:
        for name, code in (("multisex_detection", sex_fixture()), ("head_side_angle", angle_fixture()), ("fallback_grinding", grinding_fixture()),
                           ("opening_lock_window", lock_fixture(False)), ("shaft_lock_window", lock_fixture(True)),
                           ("opening_buffer_replace", lock_fixture(False, True)), ("shaft_buffer_replace", lock_fixture(True, True)),
                           ("detached_surface", detached_fixture()), ("shaft_bone_rebind", bone_fixture(False)),
                           ("opening_bone_rebind", bone_fixture(True)), ("opening_equipment_refresh", opening_refresh_fixture()),
                           ("revert_invalidates_snapshot", revert_fixture())):
            cpp, binary = Path(tmp) / (name + ".cpp"), Path(tmp) / (name + ".exe")
            cpp.write_text(code, encoding="utf-8")
            built = subprocess.run([os.environ.get("CXX", "g++"), "-std=c++23", "-pthread", str(cpp), "-o", str(binary)], check=False)
            if built.returncode:
                failures.append((name, "compile failed"))
                continue
            tested = subprocess.run([str(binary)], check=False, timeout=10)
            if tested.returncode:
                failures.append((name, f"contract assertion failed: {tested.returncode}"))
            else:
                print(f"PASS: {name}", flush=True)
    for name, reason in failures:
        print(f"FAIL: {name}: {reason}")
    raise SystemExit(bool(failures))
