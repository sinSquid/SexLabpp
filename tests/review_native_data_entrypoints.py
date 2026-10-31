"""Public query errors, filtering and rotation-unit contracts."""
from review_native_data_core import COMMON, bedroll
from review_native_data_support import function, run
import subprocess

queries = COMMON + r'''
namespace RE {using BSFixedString=std::string;struct StaticFunctionTag{};
 struct Actor{bool invalid=false;};}
#define STATICARGS VM* a_vm, StackID a_stackID, RE::StaticFunctionTag*
namespace Registry {
 struct ActorFragment {RE::Actor* actor;
  ActorFragment(RE::Actor* a,bool):actor(a){if(!a||a->invalid)throw std::runtime_error("unsupported race");}
  static std::vector<ActorFragment> MakeFragmentList(std::vector<RE::Actor*>,std::vector<RE::Actor*>);};
 struct TagDetails {TagDetails(const std::string&){} };
 struct PositionInfo {bool CanFillPosition(RE::Actor*)const;bool CanFillPosition(const ActorFragment&)const{return true;}};
 struct Scene {bool IsCompatibleTags(const TagDetails&)const{return true;}
  std::vector<std::vector<RE::Actor*>> FindAssignments(const std::vector<ActorFragment>& f)const {
   return f.size()==1?std::vector<std::vector<RE::Actor*>>{{f[0].actor}}:std::vector<std::vector<RE::Actor*>>{};}};
 struct Library{Scene scene;static Library* GetSingleton(){static Library v;return &v;}
  const Scene* ReadScene(const std::string& id){return id=="valid"?&scene:nullptr;}};
}
namespace logger {template<class... T>void info(T&&...){} }
namespace Registry {
'''
queries += function('src/Registry/Define/Fragment.cpp', 'std::vector<ActorFragment> ActorFragment::MakeFragmentList(')
queries += function('src/Registry/Define/Animation.cpp', 'bool PositionInfo::CanFillPosition(RE::Actor*')
queries += '}\n'
queries += function('src/Papyrus/SexLabRegistry.cpp','std::vector<RE::BSFixedString> ValidateScenesA(')
queries += r'''
int main(){
 VM vm;RE::Actor good,bad{true};
 auto valid=ValidateScenesA(&vm,0,nullptr,{"missing","valid"},{&good},"",{});
 if(valid!=std::vector<std::string>{"valid"})return 1;
 try{
  if(!ValidateScenesA(&vm,0,nullptr,{"valid"},{&bad},"",{}).empty())return 2;
  if(Registry::PositionInfo{}.CanFillPosition(&bad))return 3;
 }catch(const std::exception&){return 4;}
 return 0;
}
'''

expressions = COMMON + r'''
namespace RE {using BSFixedString=std::string;struct StaticFunctionTag{};
 namespace SEXES {enum SEX{kMale,kFemale,kNone=-1};}
 struct Base{SEXES::SEX sex;SEXES::SEX GetSex()const{return sex;}};
 struct Actor{Base base;Base* GetActorBase(){return &base;}};}
namespace Util {std::vector<std::string_view> StringSplit(std::string_view s,const char*){return {s};}}
namespace Registry {
 struct TagData{std::string tag;bool HasTag(const std::string& query)const{return tag==query;}};
 struct TagDetails{std::string query;TagDetails(const std::vector<std::string_view>& list):query(list[0]){}
  bool MatchTags(const TagData& tags)const{return query==tags.tag;}};
 struct Expression{std::string id;bool enabled;TagData tags;std::vector<int> data[2];
  bool IsEnabled()const{return enabled;}};
 struct Library{std::vector<Expression> profiles;static Library* GetSingleton(){static Library v;return &v;}
  void ForEachExpression(std::function<bool(const Expression&)> visit){for(auto& p:profiles)if(visit(p))return;}};
}
enum ExpressionStatus{None,Submissive,Dominant};
'''
expressions += function('src/Papyrus/sslObject/sslExpressionSlots.cpp','std::vector<RE::BSFixedString> GetExpressionsByStatus(')
expressions += function('src/Papyrus/sslObject/sslExpressionSlots.cpp','std::vector<RE::BSFixedString> GetExpressionsByTags(')
expressions += r'''
int main(){
 VM vm;RE::Actor female{{RE::SEXES::kFemale}};
 Registry::Library::GetSingleton()->profiles={
  {"normal",true,{"Normal"},{{1},{1}}},
  {"disabled",false,{"Normal"},{{1},{1}}},
  {"male-only",true,{"Normal"},{{1},{}}},
  {"victim",true,{"Victim"},{{1},{1}}}};
 if(GetExpressionsByStatus(&vm,0,nullptr,&female,None)!=std::vector<std::string>{"normal"})return 1;
 if(GetExpressionsByTags(&vm,0,nullptr,&female,"Normal")!=std::vector<std::string>{"normal"})return 2;
 if(GetExpressionsByStatus(&vm,0,nullptr,&female,Submissive)!=std::vector<std::string>{"victim"})return 3;
 return 0;
}
'''

offsets = bedroll[:bedroll.index('int main()')] + r'''
namespace RE {using BSFixedString=std::string;struct StaticFunctionTag{};}
#define STATICARGS VM* a_vm, StackID a_stackID, RE::StaticFunctionTag*
#define POSITION(ret) if(n<0 || size_t(n)>=scene->positions.size()){return ret;}
namespace Registry {
 enum CoordinateType:uint8_t{X,Y,Z,R,Total};
 struct Transform{Coordinate _offset{0,0,0,0};
  void SetOffset(const Coordinate&);void SetOffset(float,CoordinateType);};
'''
offsets += function('src/Registry/Define/Transform.cpp','void Transform::SetOffset(const Coordinate&')
offsets += function('src/Registry/Define/Transform.cpp','void Transform::SetOffset(float a_value,')
offsets += r'''
 struct Position{Transform offset;};
 struct Stage{std::vector<Position> positions{1};};
 struct Scene{Stage stage;std::vector<Position> positions{1};
  Stage* GetStageByID(const std::string&){return &stage;}
  void ForEachStage(std::function<bool(Stage*)> visit){visit(&stage);}};
 struct Library{Scene scene;static Library* GetSingleton(){static Library v;return &v;}
  bool EditScene(const std::string&,std::function<void(Scene*)> visit){visit(&scene);return true;}};
}
'''
offsets += function('src/Papyrus/SexLabRegistry.cpp','void SetStageOffsetA(')
offsets += function('src/Papyrus/SexLabRegistry.cpp','void SetStageOffset(')
offsets += r'''
int main(){
 VM vm;
 auto& offset=Registry::Library::GetSingleton()->scene.stage.positions[0].offset._offset;
 SetStageOffsetA(&vm,0,nullptr,"scene","stage",0,{1,2,3,90});
 if(std::abs(offset.rotation-std::numbers::pi_v<float>/2)>0.0001f)return 1;
 SetStageOffset(&vm,0,nullptr,"scene","stage",0,180,Registry::R);
 if(std::abs(offset.rotation-std::numbers::pi_v<float>)>0.0001f)return 2;
 return 0;
}
'''

if __name__ == '__main__':
    failures=[]
    for name,code in [('query_boundaries',queries),('expression_queries',expressions),('offset_units',offsets)]:
        try: run(name,code)
        except subprocess.CalledProcessError: failures.append(name)
    if failures: raise AssertionError('Contract failures: '+', '.join(failures))
