"""Exercise the real Papyrus request dispatch and instance creation/cancellation bodies."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def function(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

native = (ROOT / 'src/Papyrus/sslThreadModel.cpp').read_text(encoding='utf-8')
thread = (ROOT / 'src/Thread/Thread.cpp').read_text(encoding='utf-8')
create = function(thread, 'void Instance::CreateInstance(')
destroy = function(thread, 'void Instance::DestroyInstance(')
reserve = function(thread, 'std::uint64_t Instance::ReserveCreation(') if 'Instance::ReserveCreation(' in thread else ''
declarations = '\n'.join('static ' + body.split('{', 1)[0].replace('Instance::', '') + ';' for body in [create, destroy, reserve] if body)
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <format>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <ranges>
#include <string>
#include <vector>
namespace RE { using BSFixedString=std::string; struct Actor{}; struct TESQuest {unsigned formID=1;}; struct PlayerCharacter {static PlayerCharacter* GetSingleton(){return nullptr;}}; }
struct VM {void TraceStack(const char*,int){}};
#define QUESTARGS [[maybe_unused]] VM* a_vm, [[maybe_unused]] int a_stackID, RE::TESQuest* a_qst
namespace logger {template<class...T>void warn(T&&...){} template<class...T>void error(T&&...){} }
namespace Registry {struct Scene{}; struct Library {static Library* GetSingleton(){static Library lib;return &lib;} const Scene* GetSceneById(const std::string&){static Scene s;return &s;}};}
namespace Hooks {void SetWeaponDrawBlocked(bool){}}
namespace Interface {
struct SceneHUD {static SceneHUD& GetSingleton(){static SceneHUD h;return h;} void SetSpeedControl(RE::TESQuest*,bool){}};
struct FurnSelectMenu {static FurnSelectMenu& GetSingleton(){static FurnSelectMenu m;return m;} void CancelForThread(RE::TESQuest*){}};
struct StageSelectMenu {static StageSelectMenu& GetSingleton(){static StageSelectMenu m;return m;} void CancelForThread(RE::TESQuest*){}};
}
struct ControlledThread {
 static inline std::vector<std::function<void()>> jobs;
 explicit ControlledThread(std::function<void()> f){jobs.push_back(std::move(f));}
 void detach(){}
 static void Run(size_t index=0){auto f=std::move(jobs.at(index));jobs.erase(jobs.begin()+index);f();}
};
struct Instance {
 using FurniturePreference=int;
 using SceneMapping=std::array<std::vector<const Registry::Scene*>,3>;
 RE::TESQuest* linkedQst; RE::TESQuest* pendingQst=nullptr;
 static inline std::recursive_mutex _mInstances;
 static inline std::map<RE::TESQuest*,std::uint64_t> creationGenerations;
 static inline std::vector<std::unique_ptr<Instance>> instances,pendingInstances;
 static inline int constructed=0,successes=0,failures=0;
 Instance(RE::TESQuest* q,const std::vector<RE::Actor*>&,const SceneMapping&,FurniturePreference,std::uint64_t=0):linkedQst(q){++constructed;}
 void* GetPosition(RE::PlayerCharacter*){return nullptr;}
 void ReleaseAnimations(){} void RestoreActorAlphas(){}
 static void RestorePreparedActors(RE::TESQuest*){}
 static void DispatchContinueSetup(RE::TESQuest*,bool ok){ok?++successes:++failures;}
DECLARATIONS
};
namespace Thread {using Instance=::Instance;}
'''.replace('DECLARATIONS', declarations)
code += reserve + create + destroy
request = function(native, 'void CreateInstance(QUESTARGS,').replace('void CreateInstance(', 'void RequestCreateInstance(', 1).replace('std::thread(', 'ControlledThread(')
code += request
code += r'''
int main(){
 RE::TESQuest quest; VM vm;
 auto request=[&](){RequestCreateInstance(&vm,0,&quest,{},{},{},{},0);};
 request();
 Instance::DestroyInstance(&quest,false);
 ControlledThread::Run();
 std::cout << "cancel-before-worker: constructed=" << Instance::constructed << ", active=" << Instance::instances.size() << std::endl;
 assert(Instance::constructed==0 && Instance::instances.empty() && Instance::successes==0 && Instance::failures==0);
 request();
 Instance::DestroyInstance(&quest,false);
 request();
 ControlledThread::Run(1);
 assert(Instance::instances.size()==1 && Instance::successes==1);
 ControlledThread::Run(0);
 assert(Instance::instances.size()==1 && Instance::successes==1 && Instance::failures==0);
 Instance::DestroyInstance(&quest,false);
 std::cout << "PASS: stale detached work cannot recreate cancelled instances or fail a reused quest" << std::endl;
}
'''
with tempfile.TemporaryDirectory(prefix='slpp-creation-') as tmp:
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source, binary = Path(tmp)/'test.cpp', Path(tmp)/'test'
    source.write_text(code, encoding='utf-8')
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++23','-pthread',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=10)
