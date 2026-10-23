"""Execute production validation/dynamic-read prefix before downstream geometry math."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/Interaction/NiSurface/SurfaceCache.cpp').read_text()
update=function(source,'std::optional<OpeningShape> TrackedOpening::Update()')
prefix=update[:update.index('        for (auto& bone : bones)')]
prefix+=' return OpeningShape{};\n}\n'
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <memory>
#include <optional>
#include <string>
#include <vector>
namespace DirectX {
struct XMVECTOR{float x,y,z;};struct XMFLOAT3{float x,y,z;};
int reads=0;
void XMStoreFloat3(XMFLOAT3* out,const XMVECTOR& v){++reads;*out={v.x,v.y,v.z};}
}
namespace RE {
struct NiAVObject:std::enable_shared_from_this<NiAVObject>{};
struct NiSkinData{};struct NiSkinPartition{uint32_t vertexCount=4,numPartitions=1;};
struct NiSkinInstance {std::shared_ptr<NiSkinData> skinData;std::shared_ptr<NiSkinPartition> skinPartition;bool bones=true;};
struct BSGeometry:std::enable_shared_from_this<BSGeometry> {
 virtual ~BSGeometry()=default;bool parent=true;
 struct {std::shared_ptr<NiSkinInstance> skinInstance;} runtime;
 auto& GetGeometryRuntimeData(){return runtime;}
};
struct BSDynamicTriShape:BSGeometry {
 struct {void* dynamicData=nullptr;int lock=0;uint32_t dataSize=64;} dynamic;
 auto& GetDynamicTrishapeRuntimeData(){return dynamic;}
};
bool bufferLocked=false;
struct BSSpinLockGuard{explicit BSSpinLockGuard(int&){assert(!bufferLocked);bufferLocked=true;}~BSSpinLockGuard(){bufferLocked=false;}};
}
template<class T,class U>T netimmerse_cast(U* p){return dynamic_cast<T>(p);}
struct OpeningShape{};
struct TrackedOpening {
 struct Vec{float x,y,z;};struct Sample{uint16_t vertex;Vec local;};struct Landmark{std::vector<Sample> samples;};
 std::shared_ptr<RE::BSGeometry> geometry;
 RE::NiSkinInstance* skinInstance=nullptr;
 std::shared_ptr<RE::NiSkinData> boundSkinData;
 std::shared_ptr<RE::NiSkinPartition> boundPartition;
 uint32_t boundVertexCount=4,boundDynamicSize=64;bool usesDynamicBuffer=true;
 std::shared_ptr<RE::NiAVObject> deep=std::make_shared<RE::NiAVObject>();
 std::array<std::shared_ptr<RE::NiAVObject>,2> boundTargets;
 std::string boundModelPath,boundShapeName;
 std::vector<Landmark> landmarks{{{{1,{}}}},{{{3,{}}}}};
 std::optional<OpeningShape> Update();
 bool RefreshBinding();
 bool Bind(RE::BSGeometry* input,std::string_view,std::string_view,const std::array<RE::NiAVObject*,2>&,RE::NiAVObject* node){
  assert(!RE::bufferLocked);
  auto skin=input->runtime.skinInstance;
  if(!skin||!skin->skinData||!skin->skinPartition||skin->skinPartition->vertexCount<4)return false;
  geometry=input->shared_from_this();skinInstance=skin.get();deep=node->shared_from_this();
  boundSkinData=skin->skinData;boundPartition=skin->skinPartition;boundVertexCount=boundPartition->vertexCount;
  auto* dyn=dynamic_cast<RE::BSDynamicTriShape*>(input);
  usesDynamicBuffer=dyn&&dyn->dynamic.dynamicData;
  boundDynamicSize=usesDynamicBuffer?dyn->dynamic.dataSize:0;
  return true;
 }
};
'''+function(source,'bool TrackedOpening::RefreshBinding()')+prefix+r'''
int main(){
 auto geometry=std::make_shared<RE::BSDynamicTriShape>();
 auto skin=std::make_shared<RE::NiSkinInstance>();
 skin->skinData=std::make_shared<RE::NiSkinData>();skin->skinPartition=std::make_shared<RE::NiSkinPartition>();
 geometry->runtime.skinInstance=skin;
 DirectX::XMVECTOR vertices[4]{};geometry->dynamic.dynamicData=vertices;
 TrackedOpening value;value.geometry=geometry;value.skinInstance=skin.get();
 value.boundSkinData=skin->skinData;value.boundPartition=skin->skinPartition;
 assert(value.Update()&&DirectX::reads==2);
 auto reject=[&]{DirectX::reads=0;assert(!value.Update()&&DirectX::reads==0);};
 skin->skinPartition->vertexCount=2;reject();skin->skinPartition->vertexCount=4;
 skin->skinPartition=std::make_shared<RE::NiSkinPartition>();reject();skin->skinPartition=value.boundPartition;
 skin->skinData=std::make_shared<RE::NiSkinData>();reject();skin->skinData=value.boundSkinData;
 geometry->dynamic.dataSize=16;reject();geometry->dynamic.dataSize=64;
 geometry->dynamic.dynamicData=nullptr;reject();geometry->dynamic.dynamicData=vertices;
 value.landmarks[0].samples[0].vertex=4;reject();value.landmarks[0].samples[0].vertex=1;
 geometry->parent=false;reject();geometry->parent=true;
 DirectX::XMVECTOR next[4]{};geometry->dynamic.dynamicData=next;
 value.Update();
 assert(value.Update()); // Rebinding finishes before the next frame reads.
 value.usesDynamicBuffer=false;value.boundDynamicSize=0;
 DirectX::reads=0;assert(!value.Update()&&DirectX::reads==0);
 assert(value.usesDynamicBuffer&&value.Update()); // static -> dynamic recovers
 geometry->dynamic.dataSize=128;
 assert(!value.Update());assert(value.boundDynamicSize==128&&value.Update());
}
'''
run('geometry_binding',code)
