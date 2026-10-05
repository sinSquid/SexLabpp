"""Actual finalization/profile functions and limited Papyrus execution; no engine ABI claim."""
import os, subprocess
from pathlib import Path
from source_regressions import ROOT,function,run
from full_sixth_scripts import helper,Array

def source(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
    return (ROOT/path).read_text()

cpp=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <ranges>
#include <shared_mutex>
#include <stdexcept>
#include <thread>
#include <vector>
namespace RE {struct TESQuest{unsigned formID=1;};}
namespace logger{template<class...T>void error(T&&...){} }
namespace SKSE {
 inline thread_local bool inTask=false;
 struct Tasks{bool fail=false;std::vector<std::function<void()>> tasks;void AddTask(std::function<void()> f){if(fail)throw std::runtime_error("queue rejected");tasks.push_back(std::move(f));}void flush(){auto q=std::move(tasks);tasks.clear();inTask=true;for(auto& f:q)f();inTask=false;}};
 Tasks* GetTaskInterface(){static Tasks t;return &t;}
}
namespace Thread {struct Instance{
 RE::TESQuest* linkedQst=nullptr;int32_t startupRequest=1;
 std::shared_ptr<std::atomic_bool> creationCancelled=std::make_shared<std::atomic_bool>(false);
 bool fail=false;static inline int finalized=0,success=0,failure=0;
 static inline std::shared_mutex _mInstances;
 static inline unsigned generation=0;
 static unsigned GetWorldGeneration(){return generation;}
 static inline std::vector<std::shared_ptr<Instance>> pendingInstances,instances;
 static inline std::map<RE::TESQuest*,std::shared_ptr<std::atomic_bool>> creatingInstances;
 bool IsStartupRequest(int32_t n){return n==startupRequest;}
 void FinalizeInstanceMake(){assert(SKSE::inTask);++finalized;if(fail)throw std::runtime_error("finalize rejected");}
 static void DispatchContinueSetup(RE::TESQuest*,bool result,int32_t){result?++success:++failure;}
 static void FinalizeCenterRefSelection(RE::TESQuest*,int32_t);
};
'''+function(source('src/Thread/ThreadCtor.cpp'),'void Instance::FinalizeCenterRefSelection(')+r'''
}
int main(){using Thread::Instance;RE::TESQuest q;
 auto add=[&](int request){auto i=std::make_shared<Instance>();i->linkedQst=&q;i->startupRequest=request;Instance::pendingInstances.push_back(i);return i;};
 add(1);Instance::FinalizeCenterRefSelection(&q,1);assert(SKSE::GetTaskInterface()->tasks.size()==1&&Instance::finalized==0);
 SKSE::GetTaskInterface()->flush();assert(Instance::instances.size()==1&&Instance::success==1&&Instance::creatingInstances.empty());
 Instance::FinalizeCenterRefSelection(&q,777);SKSE::GetTaskInterface()->flush();assert(Instance::finalized==1); // missing request does not dereference quest
 add(2);Instance::FinalizeCenterRefSelection(&q,2);Instance::pendingInstances.clear();++Instance::generation;add(2);
 SKSE::GetTaskInterface()->flush();assert(Instance::finalized==1&&Instance::pendingInstances.size()==1); // same Quest/request in new world
 auto pending=Instance::pendingInstances.front();pending->fail=true;
 Instance::FinalizeCenterRefSelection(&q,2);SKSE::GetTaskInterface()->flush();assert(Instance::failure==1&&Instance::creatingInstances.empty());
 add(3);SKSE::GetTaskInterface()->fail=true;Instance::FinalizeCenterRefSelection(&q,3);assert(Instance::pendingInstances.empty()&&Instance::failure==2);
}
'''
if os.getenv('EIGHTH_CASE', 'center_finalization') == 'center_finalization':
    run('center_finalization',cpp)
if os.getenv('EIGHTH_CASE', 'center_finalization') == 'center_finalization':
    print('PASS: actual finalization runs in game task, ignores old-world/same-request work and handles queue/construction failure')

cpp=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <filesystem>
#include <limits>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
namespace fs=std::filesystem;
namespace logger{template<class...T>void error(T&&...){} }
namespace RE{using BSFixedString=std::string;namespace SEXES{enum{kTotal=2};}}
namespace std{
 string format(const char*,const string& id){return id+".yaml";}
 string format(const char*,string_view dir,const string& id){return string(dir)+"/"+id+".yaml";}
}
struct Dirty{mutable bool value=false;operator bool()const{return value;}Dirty& operator=(bool v){value=v;return *this;}int Receipt()const{return 0;}};
namespace YAML{struct Node{template<class K>Node& operator[](K){return *this;}template<class T>Node& operator=(T){return *this;}template<class T>void push_back(T){} };std::string Dump(const Node&){return "test";}}
namespace Util{
'''+function((ROOT/'src/Util/StringUtil.h').read_text(),'constexpr bool IsSafeFileStem(')+r'''
 struct SaveQueue{static inline std::vector<fs::path> paths;static SaveQueue& Get(){static SaveQueue q;return q;}void Submit(fs::path p,std::string,int){paths.push_back(std::move(p));}};
}
namespace Registry{
struct Expression{
 enum{MoodType=30,Total=32};std::string id;uint8_t version=0;mutable Dirty has_edits;bool enabled=true;int scaling=0;
 struct Tags{std::vector<std::string> AsVector()const{return {};}}tags;
 std::vector<std::array<float,32>> data[2];
 Expression(const std::string& name):id(name){}
 std::string GetId()const{return id;}
 void UpdateValues(bool,int,const std::vector<float>&);void Save(std::string_view,bool)const;
};
struct Library{
 mutable std::shared_mutex _mExpressions;std::map<std::string,Expression> expressions;
 bool CreateExpression(const RE::BSFixedString&);void SaveExpressions()const noexcept;
};
'''+function(source('src/Registry/Define/Expression.cpp'),'void Expression::UpdateValues(')+function(source('src/Registry/Define/Expression.cpp'),'void Expression::Save(')+function(source('src/Registry/Library.cpp'),'bool Library::CreateExpression(')+'\nstatic constexpr const char* EXPRESSION_PATH="profiles";\n'+function(source('src/Registry/Library_SaveLoad.cpp'),'void Library::SaveExpressions(')+r'''
}
int main(){
 Registry::Library library;
 for(auto id: {"",".","..","../escape","..\\escape","C:escape","a/b","a\\b","bad?name"}){
  assert(!library.CreateExpression(id));
  Registry::Expression e{id};bool rejected=false;try{e.Save("profiles",true);}catch(const std::invalid_argument&){rejected=true;}assert(rejected&&Util::SaveQueue::paths.empty());
 }
 for(auto id:{"Normal","Display name","名字","a.b","trailing.","trailing "})assert(library.CreateExpression(id));
 assert(!library.CreateExpression("Normal"));
 Registry::Expression e{"Normal"};e.Save("profiles",true);assert(Util::SaveQueue::paths.back()==fs::path("profiles/Normal.yaml"));
 Registry::Library saving;
 Registry::Expression bad{"../outside"},good{"Good"};bad.has_edits=true;good.has_edits=true;
 saving.expressions.emplace("A",bad);saving.expressions.emplace("B",good);Util::SaveQueue::paths.clear();
 saving.SaveExpressions();assert(Util::SaveQueue::paths.size()==1&&Util::SaveQueue::paths.front()==fs::path("profiles/Good.yaml"));
 std::vector<float> values(32,0.25f);e.UpdateValues(false,1,values);auto old=e.data[0];e.has_edits=false;
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()}){
  values[31]=bad;e.UpdateValues(false,3,values);assert(e.data[0]==old&&!e.has_edits);
 }
 values[31]=0.5f;e.UpdateValues(false,3,values);assert(e.data[0].size()==4&&e.data[0][3][31]==0.5f&&e.has_edits);
}
'''
if os.getenv('EIGHTH_CASE', 'expression_boundaries') == 'expression_boundaries':
    run('expression_boundaries',cpp)
if os.getenv('EIGHTH_CASE', 'expression_boundaries') == 'expression_boundaries':
    print('PASS: actual profile creation/save reject unsafe IDs, safe paths stay under root, nonfinite updates preserve old data')

cpp=r'''
#include <cassert>
#include <filesystem>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
namespace fs=std::filesystem;
namespace logger{template<class...T>void error(T&&...){} }
namespace std{
 string format(const char*,const char* name,string_view hash){return string(name)+"_"+string(hash)+".yaml";}
 string format(const char*,const char* dir,char* name,string_view hash){return string(dir)+"/"+name+"_"+string(hash)+".yaml";}
}
namespace YAML{struct Node{Node& operator[](const std::string&){return *this;}};std::string Dump(const Node&){return "test";}}
namespace Util{
'''+function((ROOT/'src/Util/StringUtil.h').read_text(),'constexpr bool IsSafeFileStem(')+r'''
 struct SaveQueue{static inline std::vector<fs::path> paths;static SaveQueue& Get(){static SaveQueue q;return q;}void Submit(fs::path p,std::string){paths.push_back(std::move(p));}};
}
namespace Registry{
struct Scene{std::string id="S";static inline int saved=0;void Save(YAML::Node&){++saved;}};
struct Package{std::string name,hash;std::vector<std::shared_ptr<Scene>> scenes{std::make_shared<Scene>()};std::string GetName()const{return name;}std::string_view GetHash()const{return hash;}};
struct Library{mutable std::shared_mutex _mScenes;std::vector<std::shared_ptr<Package>> packages;void SaveScenes()const noexcept;};
static constexpr const char* SCENE_USER_CONFIG="settings";
'''+function(source('src/Registry/Library_SaveLoad.cpp'),'void Library::SaveScenes(')+r'''
}
int main(){Registry::Library l;
 for(auto name:{"../outside","..\\outside","","safe","Title."}){auto p=std::make_shared<Registry::Package>();p->name=name;p->hash="ABCD";l.packages.push_back(p);}
 auto p=std::make_shared<Registry::Package>();p->name="safe";p->hash="../H";l.packages.push_back(p);
 l.SaveScenes();assert(Util::SaveQueue::paths.size()==3&&Registry::Scene::saved==3);
 assert(Util::SaveQueue::paths[0]==fs::path("settings/_ABCD.yaml"));
 assert(Util::SaveQueue::paths[1]==fs::path("settings/safe_ABCD.yaml"));
 assert(Util::SaveQueue::paths[2]==fs::path("settings/Title._ABCD.yaml"));
}
'''
if os.getenv('EIGHTH_CASE', 'scene_export_boundaries') == 'scene_export_boundaries':
    run('scene_export_boundaries',cpp)
if os.getenv('EIGHTH_CASE', 'scene_export_boundaries') == 'scene_export_boundaries':
    print('PASS: actual SaveScenes skips invalid package name/hash, retains normal filename and saves valid neighbors')

class Actor:
    def __init__(self):self.moods=[];self.phonemes=[];self.modifiers=[]
    def SetExpressionOverride(self,*args):self.moods.append(args)
    def SetExpressionPhoneme(self,*args):self.phonemes.append(args)
    def SetExpressionModifier(self,*args):self.modifiers.append(args)

if os.getenv('EIGHTH_CASE', 'script') == 'script':
    for current_id,current_strength,target_id,target_strength,open_mouth,changed in [
        (7,.5,7,.5,False,False),(7,.5,8,.5,False,True),(7,.5,7,.6,False,True),(7,.5,8,.6,True,False)]:
        actor=Actor();calls=[]
        def get(actor, id_only):calls.append(id_only);return current_id if id_only else current_strength
        apply=helper('sslBaseExpression','ApplyPresetFloatsLegacy','ActorRef, Preset, IsMouthOpen',{
            'GetExpression':get,'GetPhoneme':lambda *a:0,'GetModifier':lambda *a:0})
        preset=Array([0.0]*32);preset[30]=target_id;preset[31]=target_strength
        apply(actor,preset,open_mouth)
        assert actor.moods==([(target_id,int(target_strength*100))] if changed else [])
        assert len(calls)==2
        apply(None,preset,False);apply(actor,Array([0.0]*31),False);assert len(calls)==2
    print('PASS: actual Papyrus mood predicate switches different IDs, skips no-op/open-mouth override and removes redundant native reads (limited translator)')
