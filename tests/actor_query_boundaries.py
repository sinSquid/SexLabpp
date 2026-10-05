"""Real actor-list and position entry functions, with engine construction stand-ins."""
from source_regressions import ROOT, function, run

fragment = (ROOT/'src/Registry/Define/Fragment.cpp').read_text()
animation = (ROOT/'src/Registry/Define/Animation.cpp').read_text()
code = r'''
#include <algorithm>
#include <cassert>
#include <stdexcept>
#include <string>
#include <vector>
namespace std::ranges {template<class C,class V>bool contains(const C& c,const V& v){return std::find(c.begin(),c.end(),v)!=c.end();}}
namespace logger {template<class...T>void warn(T&&...){} }
namespace RE {struct Actor{bool supported=true;};template<class T>using reference_array=std::vector<T>&;}
struct VM {void TraceStack(const char*,int){}};
#define STATICARGS VM* a_vm, int a_stackID, void*
namespace Registry {
struct ActorFragment {
 static inline int constructions=0;
 static constexpr size_t MAX_ACTOR_COUNT=5;
 RE::Actor* actor;bool submissive;
 ActorFragment(RE::Actor* a,bool s):actor(a),submissive(s){
  ++constructions;
  if(!a)throw std::logic_error("null reached engine constructor");
  if(!a->supported)throw std::runtime_error("unsupported actor data");
 }
 static std::vector<ActorFragment> MakeFragmentList(std::vector<RE::Actor*>,std::vector<RE::Actor*>);
};
struct PositionInfo {
 bool CanFillPosition(RE::Actor*)const;
 bool CanFillPosition(const ActorFragment&)const{return true;}
};
struct Scene {
 bool compatible;
 std::vector<std::vector<RE::Actor*>> FindAssignments(const std::vector<ActorFragment>& f)const{
  if(!compatible||f.size()!=2)return {};
  return {{f[1].actor,f[0].actor}};
 }
};
struct Library {
 static Library* GetSingleton(){static Library l;return &l;}
 const Scene* GetSceneById(const std::string& id)const{
  static Scene bad{false},good{true};
  return id=="bad"?&bad:id=="good"?&good:nullptr;
 }
};
'''
code += function(fragment,'std::vector<ActorFragment> ActorFragment::MakeFragmentList(')
code += function(animation,'bool PositionInfo::CanFillPosition(RE::Actor*')
code += '\n}\n'
registry = (ROOT/'src/Papyrus/SexLabRegistry.cpp').read_text()
for signature in ('int32_t SortBySceneEx(', 'int32_t SortBySceneExA('):
    code += function(registry,signature)+'\n'
code += r'''
int main(){
 RE::Actor a,b,unsupported;unsupported.supported=false;
 using Registry::ActorFragment;
 auto result=ActorFragment::MakeFragmentList({&a,&b},{&b});
 assert(result.size()==2&&!result[0].submissive&&result[1].submissive);
 assert(ActorFragment::MakeFragmentList({&a,&a},{}).empty());
 assert(ActorFragment::MakeFragmentList({&a,nullptr},{}).empty());
 assert(ActorFragment::MakeFragmentList({&a,&unsupported},{}).empty());
 assert(ActorFragment::MakeFragmentList({&a,&b,&a,&b,&a,&b},{}).empty());
 assert(ActorFragment::MakeFragmentList({},{}).empty());
 Registry::PositionInfo position;
 assert(position.CanFillPosition(&a));
 assert(!position.CanFillPosition(nullptr));
 assert(!position.CanFillPosition(&unsupported));
 VM vm;std::vector<RE::Actor*> actors{&a,&b};
 ActorFragment::constructions=0;
 assert(SortBySceneEx(&vm,0,nullptr,actors,&b,{"bad","bad","good"})==2);
 assert(ActorFragment::constructions==2&&actors[0]==&b&&actors[1]==&a);
 ActorFragment::constructions=0;
 assert(SortBySceneExA(&vm,0,nullptr,actors,{&b},{"bad","bad","good"})==2);
 assert(ActorFragment::constructions==2&&actors[0]==&a&&actors[1]==&b);
 actors={&a,&a};
 assert(SortBySceneEx(&vm,0,nullptr,actors,nullptr,{"good"})==-1);
 assert(actors[0]==&a&&actors[1]==&a);
}
'''
run('actor_query_boundaries',code)
print('PASS: actual fragment-list and position entry points reject null, duplicate, oversized and unsupported actors')
