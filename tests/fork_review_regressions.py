"""Focused production-function regressions for the fork/origin maintenance changes.

Engine stand-ins test deterministic ownership/queue behavior, not Skyrim runtime behavior.
Atomic-file tests use the real filesystem and the production header.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(path, signature):
    source = (ROOT / path).read_text(encoding='utf-8')
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def run(name, source, directory):
    cpp, binary = directory / (name + '.cpp'), directory / name
    cpp.write_text(source, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', '-pthread',
                    '-I', str(ROOT / 'src'), '-Wall', '-Wextra', '-Werror', '-Wno-unknown-pragmas',
                    str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary), str(directory / name)], check=True, timeout=30)
    print('PASS:', name, flush=True)


common = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <ranges>
#include <shared_mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>
namespace RE {using BSFixedString=std::string;}
namespace logger {
 template<class... T>void error(const char*,T&&...){}
 template<class... T>void info(const char*,T&&...){}
 template<class... T>void warn(const char*,T&&...){}
}
'''

ui = common + r'''
namespace Registry {
 struct TagData {
  std::vector<RE::BSFixedString> values;
  void AddAnnotation(RE::BSFixedString s){if(std::ranges::find(values,s)==values.end())values.push_back(s);}
  const auto& GetAnnotations()const{return values;}
  void SetAnnotations(const std::vector<RE::BSFixedString>& v){values=v;}
 };
 struct Scene {TagData tags;};
 struct AnimPackage {};
 struct Library {
  Scene scene;int edits=0;bool exists=true;
  mutable std::shared_mutex _mScenes;
  std::unordered_map<const Scene*,const AnimPackage*> scenePackages;
  static Library* GetSingleton(){static Library v;return &v;}
  bool EditScene(const RE::BSFixedString&,std::function<void(Scene*)> f){if(!exists)return false;++edits;f(&scene);return true;}
  const AnimPackage* GetPackageFromScene(const Scene*)const;
 };
}
struct SceneEntry {std::string annotBuf,annotations,id;};
struct SceneSelectPanel {void OnAnnotationSave(SceneEntry&);};
using namespace Registry;
'''
ui += function('src/Thread/Interface/Elements/SceneSelectPanel.cpp', 'void SceneSelectPanel::OnAnnotationSave(')
ui += function('src/Registry/Library.cpp', 'const AnimPackage* Library::GetPackageFromScene(')
ui += r'''
int main(){
 auto* lib=Library::GetSingleton();SceneSelectPanel panel;
 for(int i=0;i<40;++i)lib->scene.tags.AddAnnotation(std::to_string(i));
 SceneEntry entry{"  new, second, new, ,last  ","old","id"};panel.OnAnnotationSave(entry);
 assert((lib->scene.tags.values==std::vector<std::string>{"new","second","last"}));
 assert(lib->edits==1&&entry.annotations=="new, second, new, ,last");
 panel.OnAnnotationSave(entry);assert(lib->edits==1);
 entry.annotBuf="   ";panel.OnAnnotationSave(entry);assert(lib->scene.tags.values.empty());
 lib->exists=false;entry.annotBuf="missing";panel.OnAnnotationSave(entry);assert(entry.annotations.empty());
 AnimPackage a,b;Scene x,y,missing;
 lib->scenePackages.emplace(&x,&a);lib->scenePackages.emplace(&y,&b);
 assert(lib->GetPackageFromScene(&x)==&a&&lib->GetPackageFromScene(&y)==&b);
 assert(!lib->GetPackageFromScene(&missing)&&!lib->GetPackageFromScene(nullptr));
}
'''

reset = common + r'''
namespace RE {
 enum class FormType {ActorCharacter,Other};
 struct Form {FormType type;unsigned formID;bool IsNot(FormType t){return type!=t;}};
 struct TESResetEvent {Form* object;};
 template<class T>struct BSTEventSource {};
}
enum class EventResult {kContinue};
struct StatisticsData {
 std::vector<unsigned> deleted;
 void DeleteStatistics(unsigned id){deleted.push_back(id);}
 EventResult ProcessEvent(const RE::TESResetEvent*,RE::BSTEventSource<RE::TESResetEvent>*);
};
'''
reset += function('src/Registry/Stats.cpp', 'StatisticsData::EventResult StatisticsData::ProcessEvent(const RE::TESResetEvent*').replace(
    'StatisticsData::EventResult', 'EventResult', 1)
reset += r'''
int main(){
 StatisticsData data;data.ProcessEvent(nullptr,nullptr);
 RE::TESResetEvent none{nullptr};data.ProcessEvent(&none,nullptr);
 RE::Form actor{RE::FormType::ActorCharacter,42},object{RE::FormType::Other,43};
 RE::TESResetEvent a{&actor},b{&object};data.ProcessEvent(&a,nullptr);data.ProcessEvent(&b,nullptr);
 assert((data.deleted==std::vector<unsigned>{42}));
}
'''

lifecycle = common + r'''
namespace RE {
 struct TESQuest {unsigned formID;};
 struct PlayerCharacter {static PlayerCharacter* GetSingleton(){return nullptr;}};
}
namespace SKSE {
 struct Tasks {std::vector<std::function<void()>> pending;void AddTask(std::function<void()> f){pending.push_back(f);}
  void Drain(){auto q=std::move(pending);pending.clear();for(auto& f:q)f();}};
 Tasks* GetTaskInterface(){static Tasks t;return &t;}
}
namespace Hooks {void SetWeaponDrawBlocked(bool){}}
namespace Interface {struct SceneHUD {
 static SceneHUD& GetSingleton(){static SceneHUD h;return h;}void SetSpeedControl(RE::TESQuest*,bool){}
};}
struct Instance {
 RE::TESQuest* linkedQst;RE::TESQuest* pendingQst;
 using SceneMapping=int;using FurniturePreference=int;
 static inline std::shared_mutex _mInstances;
 static inline std::vector<std::unique_ptr<Instance>> instances,pendingInstances;
 static inline std::map<RE::TESQuest*,std::uint64_t> creationGenerations;
 static inline int finalized=0,successes=0,failures=0;
 static inline std::function<void()> duringFinalize,duringConstruct;
 static inline bool throwFinalize=false;
 Instance(RE::TESQuest* q,const std::vector<RE::Actor*>&,int,int):linkedQst(q),pendingQst(q){if(duringConstruct)duringConstruct();}
 static Instance* GetInstance(RE::TESQuest* q){for(auto& p:instances)if(p->linkedQst==q)return p.get();return nullptr;}
 void* GetPosition(RE::PlayerCharacter*){return nullptr;}
 void ReleaseAnimations(){}
 static void RestorePreparedActors(RE::TESQuest*){}
 static void DispatchContinueSetup(RE::TESQuest*,bool ok){ok?++successes:++failures;}
 void FinalizeInstanceMake(){++finalized;if(duringFinalize)duringFinalize();if(throwFinalize)throw std::runtime_error("failed");}
 static void CreateInstance(RE::TESQuest*,const std::vector<RE::Actor*>,const SceneMapping&,FurniturePreference);
 static void DestroyInstance(RE::TESQuest*,bool=false);
 static void CancelPendingCreations();
 static void FinalizeCenterRefSelection(RE::TESQuest*);
};
'''
# The production API only needs Actor as a pointer in this lifecycle test.
lifecycle = lifecycle.replace('struct TESQuest {unsigned formID;};', 'struct Actor {};struct TESQuest {unsigned formID;};')
for path, sig in [
    ('src/Thread/Thread.cpp', 'void Instance::CreateInstance('),
    ('src/Thread/Thread.cpp', 'void Instance::DestroyInstance('),
    ('src/Thread/Thread.cpp', 'void Instance::CancelPendingCreations('),
    ('src/Thread/ThreadCtor.cpp', 'void Instance::FinalizeCenterRefSelection('),
]:
    lifecycle += '\n' + function(path, sig)
lifecycle += r'''
int main(){
 RE::TESQuest q{1};auto* tasks=SKSE::GetTaskInterface();
 auto create=[&](){Instance::CreateInstance(&q,{},0,0);};
 create();Instance::FinalizeCenterRefSelection(&q);Instance::FinalizeCenterRefSelection(&q);assert(Instance::finalized==0);
 tasks->Drain();assert(Instance::instances.size()==1&&Instance::successes==1&&Instance::failures==0);
 Instance::DestroyInstance(&q);
 create();Instance::FinalizeCenterRefSelection(&q);Instance::DestroyInstance(&q);
 tasks->Drain();assert(Instance::instances.empty()&&Instance::pendingInstances.empty()&&Instance::successes==1);
 // Reuse the exact same Quest after cancel: an old queued task must not consume the new pending instance.
 create();Instance::FinalizeCenterRefSelection(&q);Instance::DestroyInstance(&q);create();
 tasks->Drain();assert(Instance::instances.empty()&&Instance::pendingInstances.size()==1);
 Instance::FinalizeCenterRefSelection(&q);tasks->Drain();assert(Instance::successes==2);
 Instance::DestroyInstance(&q);
 // Cancellation during construction and immediately before publication.
 Instance::duringConstruct=[&](){Instance::DestroyInstance(&q);};create();
 Instance::duringConstruct={};assert(Instance::pendingInstances.empty());
 create();Instance::FinalizeCenterRefSelection(&q);
 Instance::duringFinalize=[&](){Instance::DestroyInstance(&q);};tasks->Drain();Instance::duringFinalize={};
 assert(Instance::instances.empty()&&Instance::successes==2);
 create();Instance::FinalizeCenterRefSelection(&q);Instance::FinalizeCenterRefSelection(&q);Instance::throwFinalize=true;tasks->Drain();
 assert(Instance::failures==1&&Instance::instances.empty());
 Instance::throwFinalize=false;create();Instance::FinalizeCenterRefSelection(&q);tasks->Drain();
 assert(Instance::instances.size()==1&&Instance::successes==3);
 Instance::DestroyInstance(&q);create();Instance::FinalizeCenterRefSelection(&q);
 Instance::CancelPendingCreations();tasks->Drain();assert(Instance::pendingInstances.empty()&&Instance::instances.empty());
 create();Instance::FinalizeCenterRefSelection(&q);tasks->Drain();assert(Instance::successes==4);
}
'''

atomic = common + r'''
#include "Util/AtomicWrite.h"
#include <fstream>
#include <thread>
std::string read(const std::filesystem::path& p){std::ifstream f(p,std::ios::binary);return {std::istreambuf_iterator<char>(f),{}};}
int main(int argc,char** argv){
 assert(argc==2);std::filesystem::path root=argv[1];root += "-files";
 const auto file=root/"settings.yaml";
 Util::AtomicWrite(file,"old complete bytes");assert(read(file)=="old complete bytes");
 Util::AtomicWrite(file,"new complete bytes");assert(read(file)=="new complete bytes");
 Util::AtomicWrite(file,"do not overwrite",false);assert(read(file)=="new complete bytes");
 const auto directory=root/"blocked";std::filesystem::create_directory(directory);
 bool failed=false;try{Util::AtomicWrite(directory,"bad");}catch(...){failed=true;}
 assert(failed&&std::filesystem::is_directory(directory)&&read(file)=="new complete bytes");
 std::vector<std::thread> writers;
 for(int i=0;i<8;++i)writers.emplace_back([&,i](){for(int n=0;n<10;++n)Util::AtomicWrite(file,std::string(8192,static_cast<char>('A'+i)));});
 for(auto& w:writers){w.join();}
 auto bytes=read(file);
 assert(bytes.size()==8192&&bytes.find_first_not_of(bytes[0])==std::string::npos);
 for(const auto& entry:std::filesystem::directory_iterator(root))assert(entry.path().filename().string().find(".tmp-")==std::string::npos);
}
'''

save = common + r'''
#include <filesystem>
#include <format>
#include <thread>
namespace fs=std::filesystem;
namespace YAML {
 struct Node {
  std::shared_ptr<std::string> bytes=std::make_shared<std::string>();
  Node operator[](const std::string&){return *this;}Node operator[](std::size_t){return *this;}
  template<class T>Node& operator=(const T&){return *this;}
  template<class T>void push_back(const T&){}
 };
 std::string Dump(const Node& n){if(n.bytes->find("bad")!=std::string::npos)throw std::runtime_error("serialize failed");return *n.bytes;}
}
struct Scene {std::string id;void Save(YAML::Node& n){*n.bytes+=id;}};
struct Package {
 std::string name;std::vector<std::unique_ptr<Scene>> scenes;
 const std::string& GetName()const{return name;}int GetHash()const{return 123;}
};
struct Library {
 static constexpr const char* SCENE_USER_CONFIG="settings";
 mutable std::shared_mutex _mScenes;
 std::vector<std::unique_ptr<Package>> packages;
 void SaveScenes()const noexcept;
};
Library library;
namespace Util {
 std::map<std::string,std::string> disk;
 void AtomicWrite(const fs::path& p,const std::string& bytes){
  bool unlocked=false;std::thread probe([&](){unlocked=library._mScenes.try_lock();if(unlocked)library._mScenes.unlock();});probe.join();assert(unlocked);
  if(p.string().find("blocked")!=std::string::npos)throw std::runtime_error("disk failed");
  disk[p.string()]=bytes;
 }
}
'''
save += function('src/Registry/Library_SaveLoad.cpp', 'void Library::SaveScenes(')
save += r'''
namespace RE::SEXES {constexpr std::size_t kTotal=2;}
struct Expression {
 std::string id;int version=0,scaling=0;bool enabled=true;mutable bool has_edits=true;
 struct Tags {std::vector<std::string> AsVector()const{return {};}} tags;
 std::vector<std::vector<int>> data[2];
 void Save(std::string_view,bool)const;
};
'''
save += function('src/Registry/Define/Expression.cpp', 'void Expression::Save(')
save += r'''
int main(){
 auto add=[](std::string name,std::string data){auto p=std::make_unique<Package>();p->name=name;p->scenes.push_back(std::make_unique<Scene>(data));library.packages.push_back(std::move(p));};
 add("first","A");add("blocked","B");add("last","C");
 Util::disk["settings\\blocked_123.yaml"]="old bytes";
 library.SaveScenes();
 assert(Util::disk["settings\\first_123.yaml"]=="A");
 assert(Util::disk["settings\\blocked_123.yaml"]=="old bytes");
 assert(Util::disk["settings\\last_123.yaml"]=="C");
 // Serializing the full batch fails before any disk writes: preserve previous files.
 library.packages[0]->scenes[0]->id="changed";add("invalid","bad");library.SaveScenes();
 assert(Util::disk["settings\\first_123.yaml"]=="A"&&!Util::disk.contains("settings\\invalid_123.yaml"));
 library.packages.pop_back();library.SaveScenes();assert(Util::disk["settings\\first_123.yaml"]=="changed");
 Expression expression;expression.id="blocked";
 bool failed=false;try{expression.Save("expressions",false);}catch(...){failed=true;}
 assert(failed&&expression.has_edits);
 expression.id="saved";expression.Save("expressions",false);assert(!expression.has_edits);
 assert(Util::disk.contains("expressions\\saved.yaml"));
}
'''

utilities = common + r'''
#include <barrier>
#include <thread>
#include <regex>
#include <cctype>
#include "Util/Random.h"
#include "Util/StringUtil.h"
#include "Util/Combinatorics.h"
int main(){
 int combinations=0;
 auto visit=[&](const std::vector<std::vector<int>::const_iterator>& values){for(auto it:values)assert(*it>0);++combinations;return Combinatorics::CResult::Next;};
 Combinatorics::ForEachCombination<int>({},visit);
 Combinatorics::ForEachCombination<int>({{1},{}},visit);assert(combinations==0);
 Combinatorics::ForEachCombination<int>({{1,2},{3,4,5}},visit);assert(combinations==6);
 std::barrier gate(8);std::vector<std::thread> workers;std::vector<const void*> engines(8);
 for(int n=0;n<8;++n)workers.emplace_back([&,n](){
  engines[n]=&Random::eng;gate.arrive_and_wait();
  for(int j=0;j<1000;++j){auto s=Random::generateUUID();assert(s.size()==36);
   for(size_t i=0;i<s.size();++i){if(i==8||i==13||i==18||i==23)assert(s[i]=='-');else assert(std::string_view("0123456789abcdef").find(s[i])!=std::string_view::npos);}
  }gate.arrive_and_wait();
 });
 for(auto& w:workers){w.join();}
 for(int i=0;i<8;++i)for(int j=i+1;j<8;++j)assert(engines[i]!=engines[j]);
 assert(Util::StringSplit("",",").empty());assert(Util::StringSplit(",,,",",").empty());
 assert((Util::StringSplitToOwned(", a ,, b ,",",")==std::vector<std::string>{"a","b"}));
 std::string s="AbC";s.push_back(static_cast<char>(0xFF));Util::ToLower(s);assert(s.substr(0,3)=="abc"&&static_cast<unsigned char>(s.back())==255);
}
'''

async_io = common + r'''
#include <chrono>
#include <condition_variable>
#include <deque>
#include <thread>
#include <atomic>
using namespace std::chrono_literals;
'''
async_io += function('src/Util/AsyncIO.cpp', 'class TaskConsumer final') + ';'
async_io += r'''
int main(){
 std::atomic<int> completed=0;
 {TaskConsumer queue;
  queue.Submit([](){throw std::runtime_error("test failure");});
  for(int i=0;i<100;++i)queue.Submit([&](){++completed;});
 }
 assert(completed==100);
 {TaskConsumer queue;queue.Submit([&](){++completed;});
  std::this_thread::sleep_for(2200ms);
  queue.Submit([&](){++completed;});
 }
 assert(completed==102);
}
'''
expression_bounds = common + r'''
#include <array>
struct Expression {
 static constexpr size_t Total=32;
 static constexpr size_t MAX_AUTOMATIC_LEVELS=4096;
 bool has_edits=false;std::vector<std::array<float,Total>> data[2];
 bool UpdateValues(bool,int,std::vector<float>);
};
'''
expression_bounds += function('src/Registry/Define/Expression.cpp', 'bool Expression::UpdateValues(')
expression_bounds += r'''
int main(){
 Expression e;e.UpdateValues(false,-1,std::vector<float>(32,1));
 assert(!e.has_edits&&e.data[0].empty());
 e.UpdateValues(false,0,std::vector<float>(31,1));assert(!e.has_edits&&e.data[0].empty());
 e.UpdateValues(true,2,std::vector<float>(32,0.5f));assert(e.has_edits&&e.data[1].size()==3&&e.data[0].empty());
 for(auto v:e.data[1][2])assert(v==0.5f);
}
'''

navtext = common + r'''
#include <charconv>
#include <cctype>
namespace RE {struct Actor {const char* GetName()const{return "Actor";}};}
'''
navtext += function('src/Thread/Interface/StageSelectMenu.cpp', 'std::string ResolveNavTextPlaceholders(')
navtext += r'''
int main(){
 RE::Actor actor;std::vector<RE::Actor*> actors{&actor,nullptr};
 assert(ResolveNavTextPlaceholders("{0}/{1}/{2}",actors)=="Actor/{}/{}");
 assert(ResolveNavTextPlaceholders("{99999999999999999999999999999999999}",actors)=="{}");
 assert(ResolveNavTextPlaceholders("{x} {} {0",actors)=="{x} {} {0");
}
'''

stream_errors = common + r'''
#include <fstream>
void configure(std::ifstream& stream){
'''
stream_errors += '\n'.join(line for line in function(
    'src/Registry/Define/Animation.cpp', 'AnimPackage::AnimPackage(').splitlines()
    if 'stream.exceptions(' in line)
stream_errors += r'''
}
int main(int argc,char** argv){
 assert(argc==2);std::string path=std::string(argv[1])+".bin";
 {std::ofstream file(path,std::ios::binary);file.put('X');}
 {std::ifstream stream(path,std::ios::binary);configure(stream);char c;stream.read(&c,1);assert(c=='X');
  bool threw=false;try{stream.read(&c,1);}catch(const std::ios_base::failure&){threw=true;}assert(threw);}
 {std::ifstream stream(path,std::ios::binary);configure(stream);
  bool threw=false;try{stream.setstate(std::ios::badbit);}catch(const std::ios_base::failure&){threw=true;}assert(threw);}
}
'''

console_output = common + r'''
#include <cstdarg>
namespace RE {struct ConsoleLog {
 std::vector<std::string> lines;
 static ConsoleLog* GetSingleton(){static ConsoleLog c;return &c;}
 void Print(const char* format,...){assert(std::string(format)=="%s");va_list args;va_start(args,format);lines.emplace_back(va_arg(args,const char*));va_end(args);}
};}
'''
console_output += function('src/Util/Misc.h', 'inline void PrintConsole(')
console_output += r'''
int main(){
 auto& lines=RE::ConsoleLog::GetSingleton()->lines;
 PrintConsole("100% %s %n");assert(lines[0]=="100% %s %n");lines.clear();
 std::string large(3500,'X');PrintConsole(large);std::string joined;
 for(auto line:lines){assert(line.size()<=951);assert(line.back()=='\n');line.pop_back();joined+=line;}
 assert(joined==large);
}
'''

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='sexlab-fork-review-') as tmp:
        directory = Path(tmp)
        for name, code in [('annotations_and_package_index', ui), ('actor_reset_filter', reset),
                           ('pending_instance_cancellation', lifecycle), ('atomic_config_files', atomic),
                           ('save_snapshot_failures', save), ('random_and_strings', utilities),
                           ('async_shutdown_and_restart', async_io), ('expression_input_bounds', expression_bounds),
                           ('menu_placeholder_overflow', navtext), ('stream_error_flags', stream_errors),
                           ('console_format_and_chunks', console_output)]:
            run(name, code, directory)
