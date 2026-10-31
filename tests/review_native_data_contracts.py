"""Public path/bed contracts using production function bodies."""
from review_native_data_core import COMMON
from review_native_data_support import ROOT, function, run
import subprocess
graph = COMMON + r'''
#include <queue>
#include <set>
namespace logger {template<class... T> void warn(T&&...) {}}
struct Stage{char id;};
struct Scene{
 enum class NodeType {None,Root,Sink,Default};
 const Stage* start_animation{};
 std::map<const Stage*,std::vector<const Stage*>> graph;
 NodeType GetStageNodeType(const Stage*)const;
 std::vector<const Stage*> GetShortestPath(const Stage*)const;
 std::vector<const Stage*> GetLongestPath(const Stage*)const;
};
'''
graph += function('src/Registry/Define/Animation.cpp', 'Scene::NodeType Scene::GetStageNodeType(')
graph += function('src/Registry/Define/Animation.cpp', 'std::vector<const Stage*> Scene::GetShortestPath(')
graph += function('src/Registry/Define/Animation.cpp', 'std::vector<const Stage*> Scene::GetLongestPath(')
graph += r'''
int main(){
 Stage a{'A'},b{'B'},c{'C'},d{'D'};
 Scene scene;scene.start_animation=&a;
 scene.graph={{&a,{&b,&c}},{&b,{&d}},{&c,{}},{&d,{&b}}};
 auto result=scene.GetLongestPath(&a);
 std::cout << "ND-20 Longest path to a sink expected AC, actual ";
 for(auto node:result)std::cout<<node->id;
 bool terminal=!result.empty()&&scene.graph.at(result.back()).empty();
 std::cout<<"; ends at sink="<<terminal<<'\n';
 scene.graph[&d].clear();auto control=scene.GetLongestPath(&a);
 if(control!=std::vector<const Stage*>{&a,&b,&d})return 2;
 return result==std::vector<const Stage*>{&a,&c}&&terminal?0:2;
}
'''

beds = COMMON + r'''
namespace RE {
 struct StaticFunctionTag{};
 struct BSFurnitureMarker {enum class AnimationType{kSleep};};
 struct Marker {struct Flags{bool all(BSFurnitureMarker::AnimationType)const{return true;}} animationType;};
 struct BSFurnitureMarkerNode {std::vector<Marker> markers;};
 struct Root {BSFurnitureMarkerNode* extra;auto GetExtraData(const char*){return extra;}};
 struct TESObjectREFR {std::string name;Root* root;bool roll=false;
  bool HasKeyword(int)const{return roll;}const char* GetName()const{return name.c_str();}Root* Get3D()const{return root;}};
}
template<class T,class U>T netimmerse_cast(U* object){return static_cast<T>(object);}
namespace GameForms {inline int FurnitureBedRoll=1;}
namespace Util {std::string CastLower(std::string text){std::ranges::transform(text,text.begin(),[](unsigned char c){return char(std::tolower(c));});return text;}}
namespace Registry {
 struct FurnitureType {
'''
beds += function('src/Registry/Define/Furniture.h','enum Value : uint32_t') + ';\n'
beds += r'''
  Value value;FurnitureType(Value v):value(v){}operator Value()const{return value;}
  static FurnitureType GetBedType(const RE::TESObjectREFR*);
 };
'''
beds += function('src/Registry/Define/Furniture.cpp', 'FurnitureType FurnitureType::GetBedType(')
beds += '}\n'
beds += function('src/Papyrus/sslLibrary/sslThreadLibrary.cpp','int32_t GetBedTypeImpl(')
beds += r'''
int main(){
 RE::BSFurnitureMarkerNode single{{{}}},doubleMarkers{{{},{}}};
 RE::Root singleRoot{&single},doubleRoot{&doubleMarkers};
 RE::TESObjectREFR english{"Bed",&singleRoot},chinese{"床",&singleRoot},doubleBed{"Double Bed",&doubleRoot};
 VM vm;auto control=GetBedTypeImpl(&vm,0,nullptr,&english);
 auto localized=GetBedTypeImpl(&vm,0,nullptr,&chinese);
 auto actualDouble=GetBedTypeImpl(&vm,0,nullptr,&doubleBed);
 if(control!=2)return 2;
 std::cout<<"ND-06 Same sleep marker: English Bed="<<control<<", Chinese 床 expected 2 actual "<<localized<<'\n';
 std::cout<<"ND-07 Double bed public code: PSC expected 3, actual "<<actualDouble<<'\n';
 return localized==2&&actualDouble==3?0:2;
}
'''


if __name__ == '__main__':
    failures=[]
    for name,code in [('cyclic_path_contract',graph),('bed_public_contract',beds)]:
        try: run(name,code)
        except subprocess.CalledProcessError: failures.append(name)
    if failures: raise AssertionError('Contract failures: '+', '.join(failures))
