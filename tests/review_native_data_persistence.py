"""Production scene settings and scale cleanup, with storage/interface stand-ins."""
from review_native_data_core import COMMON
from review_native_data_support import function, run
import subprocess

scene = COMMON + r'''
#include <memory>
#include <variant>
namespace YAML {
 enum class NodeType {Sequence,Map};
 struct Data;
 struct Node {
  std::shared_ptr<Data> p;
  Node();Node(NodeType);explicit Node(std::shared_ptr<Data> data):p(data){}
  Node operator[](const std::string&);Node operator[](const std::string&)const;
  Node operator[](size_t);Node operator[](size_t)const;
  Node& operator=(const Node&);Node& operator=(bool);Node& operator=(float);
  void push_back(const std::string&);bool IsDefined()const;bool IsSequence()const;
  size_t size()const;template<class T>T as()const;
  std::vector<Node>::iterator begin()const;std::vector<Node>::iterator end()const;
 };
 struct Data {bool defined=false,sequence=false;std::map<std::string,Node> map;
  std::vector<Node> items;std::variant<bool,float,std::string> scalar;};
 Node::Node():p(std::make_shared<Data>()){}
 Node::Node(NodeType type):Node(){p->defined=true;p->sequence=type==NodeType::Sequence;}
 Node Node::operator[](const std::string& k){p->defined=true;return p->map[k];}
 Node Node::operator[](const std::string& k)const{auto i=p->map.find(k);return i==p->map.end()?Node{}:i->second;}
 Node Node::operator[](size_t i){p->defined=p->sequence=true;if(p->items.size()<=i)p->items.resize(i+1);return p->items[i];}
 Node Node::operator[](size_t i)const{return i<p->items.size()?p->items[i]:Node{};}
 Node& Node::operator=(const Node& n){if(p!=n.p)*p=*n.p;return *this;}
 Node& Node::operator=(bool v){p->defined=true;p->scalar=v;return *this;}
 Node& Node::operator=(float v){p->defined=true;p->scalar=v;return *this;}
 void Node::push_back(const std::string& v){p->defined=p->sequence=true;Node n;n.p->defined=true;n.p->scalar=v;p->items.push_back(n);}
 bool Node::IsDefined()const{return p->defined;}bool Node::IsSequence()const{return p->sequence;}
 size_t Node::size()const{return p->items.size();}
 template<class T>T Node::as()const{return std::get<T>(p->scalar);}
 auto Node::begin()const->std::vector<Node>::iterator{return p->items.begin();}
 auto Node::end()const->std::vector<Node>::iterator{return p->items.end();}
}
namespace RE {using BSFixedString=std::string;}
namespace Registry {
 struct Transform {float value=3;bool HasChanges()const{return value!=3;}
  void Save(YAML::Node& n)const{n["value"]=value;}void Load(const YAML::Node& n){value=n["value"].as<float>();}};
 struct Tags{std::vector<std::string> annotations;const auto& GetAnnotations()const{return annotations;}
  void SetAnnotations(const std::vector<std::string>& v){annotations=v;}
  void AddAnnotation(std::string v){annotations.push_back(v);}};
 struct PositionInfo{std::vector<std::string> annotations;};
 struct Stage{std::string id="stage001";void Save(YAML::Node&)const{}void Load(const YAML::Node&){} };
 struct Scene{bool enabled=true;Transform furnitureOffset;Tags tags;
  std::vector<PositionInfo> positions{2};std::vector<std::unique_ptr<Stage>> stages;
  Scene(){stages.push_back(std::make_unique<Stage>());}
  void Save(YAML::Node&)const;void Load(const YAML::Node&);};
'''
scene += function('src/Registry/Define/Animation.cpp','void Scene::Save(')
scene += function('src/Registry/Define/Animation.cpp','void Scene::Load(')
scene += r'''
}
int main(){
 Registry::Scene before;before.furnitureOffset.value=42;before.tags.annotations={"scene-tag"};
 before.positions[0].annotations={"position-tag"};before.positions[1].annotations={};
 YAML::Node save;before.Save(save);
 Registry::Scene after;after.positions[1].annotations={"original-package-tag"};after.Load(save);
 if(after.furnitureOffset.value!=42 || after.tags.annotations!=before.tags.annotations ||
    after.positions[0].annotations!=before.positions[0].annotations || !after.positions[1].annotations.empty())return 1;
 Registry::Scene legacy;legacy.tags.annotations={"keep"};YAML::Node old;old["enabled"]=false;legacy.Load(old);
 if(legacy.enabled || legacy.furnitureOffset.value!=3 || legacy.tags.annotations!=std::vector<std::string>{"keep"})return 2;
 return 0;
}
'''

scale = COMMON + r'''
namespace RE {namespace SEXES{enum SEX{kMale,kFemale};}struct Base{SEXES::SEX GetSex(){return SEXES::kMale;}};
 struct Actor{Base base;Base* GetActorBase(){return &base;}unsigned GetFormID(){return 1;}};}
struct Settings{static inline bool bDisableScale=true;static bool ReadMCM(bool v){return v;}static void WriteMCM(bool& dst,bool v){dst=v;}};
namespace logger{template<class... T>void info(T&&...){} }
namespace SKEE {
 struct IPluginInterface{virtual ~IPluginInterface()=default;virtual unsigned GetVersion()const=0;};
 struct INiTransformInterface:IPluginInterface {static constexpr unsigned Version=2;bool applied=true;int updates=0;
  unsigned GetVersion()const override{return Version;}
  bool RemoveNodeTransformScale(RE::Actor*,bool,bool,const char*,const char*){return std::exchange(applied,false);}
  void UpdateNodeTransforms(RE::Actor*,bool,bool,const char*){++updates;}};
 namespace Legacy {using FixedString=std::string;struct OverrideVariant{enum{Scale};};
 struct INiTransformInterface:IPluginInterface {bool applied=true;int updates=0;unsigned GetVersion()const override{return 1;}
  bool RemoveNodeTransformComponent(RE::Actor*,bool,bool,const FixedString&,const FixedString&,int,int){return std::exchange(applied,false);}
  void UpdateNodeTransforms(RE::Actor*,bool,bool,const FixedString&){++updates;}};}
}
namespace Registry {struct Scale{SKEE::IPluginInterface* transformInterface;const char* basenode="NPC";const char* namekey="SexLabRegistry";
 void RemoveScale(RE::Actor*);};
'''
scale += function('src/Registry/Util/Scale.cpp','void Scale::RemoveScale(')
scale += r'''
}
int main(){
 RE::Actor actor;SKEE::INiTransformInterface modern;SKEE::Legacy::INiTransformInterface legacy;
 Registry::Scale{&modern}.RemoveScale(&actor);Registry::Scale{&legacy}.RemoveScale(&actor);
 return !modern.applied&&!legacy.applied&&modern.updates==1&&legacy.updates==1?0:1;
}
'''

if __name__ == '__main__':
    failures=[]
    for name,code in [('scene_settings_roundtrip',scene),('scale_cleanup',scale)]:
        try: run(name,code)
        except subprocess.CalledProcessError: failures.append(name)
    if failures: raise AssertionError('Contract failures: '+', '.join(failures))
