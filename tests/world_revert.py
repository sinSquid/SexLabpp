"""Actual transient-world clearing and queued-task/center dispatch with stand-ins."""
from source_regressions import ROOT,function,run
from pathlib import Path
cpp=(ROOT/'src/Thread/Thread.cpp').read_text()
code=r'''
#include <cassert>
#include <atomic>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <map>
#include <vector>
#include <cstdint>
#include <functional>
#include <future>
#include <iostream>
struct Mutex {bool held=false;void lock(){assert(!held);held=true;}void unlock(){assert(held);held=false;}};
Mutex instanceMutex;
namespace NiNode {struct NiUpdate {static inline int resets=0;static void Revert(){assert(!instanceMutex.held);++resets;}};}
namespace LegacyNiNode {struct NiUpdate {static inline int resets=0;static void Revert(){assert(!instanceMutex.held);++resets;}};}
namespace Interface {
 struct SceneHUD {static inline int resets=0;static SceneHUD& GetSingleton(){static SceneHUD h;return h;}void Destroy(){assert(!instanceMutex.held);++resets;}};
 struct FurnSelectMenu {static inline int resets=0;static FurnSelectMenu& GetSingleton(){static FurnSelectMenu h;return h;}void Revert(){assert(!instanceMutex.held);++resets;}};
 struct StageSelectMenu {static inline int resets=0;static StageSelectMenu& GetSingleton(){static StageSelectMenu h;return h;}void Revert(){assert(!instanceMutex.held);++resets;}};
}
namespace Hooks {inline bool blocked=true;void SetWeaponDrawBlocked(bool flag){blocked=flag;}}
std::mutex actorPreparationLock;std::unordered_map<int,void*> actorPreparations;
struct Instance {
 std::shared_ptr<std::atomic_bool> creationCancelled=std::make_shared<std::atomic_bool>(false);
 static inline int destroyed=0;
 ~Instance(){assert(!instanceMutex.held);++destroyed;}
 static inline Mutex& _mInstances=instanceMutex;
 static inline std::atomic<uint64_t> worldGeneration{0};
 static inline std::vector<std::shared_ptr<Instance>> instances,pendingInstances;
 static inline std::map<int,std::shared_ptr<std::atomic_bool>> creatingInstances;
 static void Revert();static void DiscardPreparedActors();
};
'''
code+=function(cpp,'void Instance::Revert(')+function((ROOT/'src/Thread/ThreadAnimation.cpp').read_text(),'void Instance::DiscardPreparedActors(')
# Actual registry clear functions, using containers with destructors checking lock release.
for namespace,path,container in [('Modern','src/Thread/NiNode/NiUpdate.cpp','_instances'),('Legacy','src/Thread/NiNode/Legacy/LegacyNiUpdate.cpp','processes')]:
 code+=f'namespace {namespace} {{ struct NiUpdate {{ static inline Mutex _m; static inline std::vector<std::shared_ptr<Instance>> {container}; static void Revert(); }};'+function((ROOT/path).read_text(),'void NiUpdate::Revert(')+'}\n'
code+=r'''
int main(){
 auto active=std::make_shared<Instance>(),pending=std::make_shared<Instance>();
 auto activeToken=active->creationCancelled,pendingToken=pending->creationCancelled,creating=std::make_shared<std::atomic_bool>(false);
 Instance::instances={active};Instance::pendingInstances={pending};Instance::creatingInstances[1]=creating;
 active.reset();pending.reset();actorPreparations[1]=reinterpret_cast<void*>(0x1); // An invalid old-world pointer must never be dereferenced.
 Instance::Revert();
 assert(activeToken->load()&&pendingToken->load()&&creating->load());
 assert(Instance::instances.empty()&&Instance::pendingInstances.empty()&&Instance::creatingInstances.empty()&&actorPreparations.empty());
 assert(Instance::worldGeneration==1&&Instance::destroyed==2&&!Hooks::blocked);
 assert(NiNode::NiUpdate::resets==1&&LegacyNiNode::NiUpdate::resets==1&&Interface::SceneHUD::resets==1);
 Instance::Revert();assert(Instance::worldGeneration==2&&Instance::destroyed==2);
 Modern::NiUpdate::_instances.push_back(std::make_shared<Instance>());Legacy::NiUpdate::processes.push_back(std::make_shared<Instance>());
 Modern::NiUpdate::Revert();Legacy::NiUpdate::Revert();assert(Instance::destroyed==4);
 std::cout<<"PASS: actual Revert cancels creators, discards old Actors/registries and releases instances outside locks\n";
}
'''
run('world_revert',code)
# Compile the actual queued native creation block, not a handwritten implementation.
source=(ROOT/'src/Papyrus/sslThreadModel.cpp').read_text();a=source.index('SKSE::GetTaskInterface()->AddTask',source.index('    void CreateInstance('));b=source.index('\n        } catch',a)
block='const auto generation = Thread::Instance::GetWorldGeneration();\n'+source[a:b]
code=r'''
#include <cassert>
#include <functional>
#include <vector>
#include <iostream>
namespace Thread {struct Instance {static inline unsigned generation=0;static inline int created=0;static unsigned GetWorldGeneration(){return generation;}static void CreateInstance(int,int,int,int,int){++created;}};}
namespace SKSE {struct Tasks {std::vector<std::function<void()>> list;void AddTask(std::function<void()> task){list.push_back(std::move(task));}};Tasks* GetTaskInterface(){static Tasks t;return &t;}}
void enqueue(){int a_qst=1,a_submissives=2,scenes=3,preference=4,request=5;
'''+block+r'''
}
int main(){enqueue();++Thread::Instance::generation;SKSE::GetTaskInterface()->list.front()();assert(Thread::Instance::created==0);enqueue();SKSE::GetTaskInterface()->list.back()();assert(Thread::Instance::created==1);std::cout<<"PASS: actual queued creation ignores tasks from a reverted world\n";}
'''
run('world_creation_task',code)
# Actual center dispatch: game-thread execution must not wait on another game task.
source=(ROOT/'src/Thread/ThreadCtor.cpp').read_text();a=source.index('        if (((bool (*)(void))Offsets::NotOnGameThread.address())())',source.index('        };',source.index('const auto initialize =')));b=source.index('        if (creationCancelled->load())',a)
block=source[a:b]
code=r'''
#include <cassert>
#include <functional>
#include <future>
#include <cstdint>
namespace Offsets {inline bool off=false;bool check(){return off;}struct {std::uintptr_t address(){return reinterpret_cast<std::uintptr_t>(&check);}} NotOnGameThread;}
namespace SKSE {struct Tasks {int queued=0;void AddTask(std::function<void()> f){++queued;f();}};Tasks* GetTaskInterface(){static Tasks t;return &t;}}
int main(){for(bool off:{false,true}){Offsets::off=off;std::promise<void> promise;auto future=promise.get_future();int ran=0;auto initialize=[&](){++ran;promise.set_value();};
'''+block+r'''
assert(ran==1&&SKSE::GetTaskInterface()->queued==(off?1:0));}}
'''
run('center_dispatch',code)
# Actual menu reset bodies; engine window calls are stand-ins.
code=r'''
#include <cassert>
#include <mutex>
#include <vector>
struct FurnSelectMenu {std::mutex _stateMutex;void* _linkedThread=reinterpret_cast<void*>(1);int _startupRequest=2;std::vector<int> _items{1};bool visible=true;void Hide(){visible=false;}void Revert();};
struct StageSelectMenu {void* _linkedThread=reinterpret_cast<void*>(1);void* _graphScene=reinterpret_cast<void*>(1);std::vector<int> _graphNodes{1},_graphEdges{1};int _graphCurrentIndex=1;bool visible=true;void Close(){visible=false;}void Revert();};
'''
for name in ('FurnSelectMenu','StageSelectMenu'):
 code+=function((ROOT/f'src/Thread/Interface/{name}.cpp').read_text(),f'void {name}::Revert(')
code+=r'''
int main(){FurnSelectMenu f;StageSelectMenu s;f.Revert();s.Revert();f.Revert();s.Revert();assert(!f.visible&&!f._linkedThread&&!f._startupRequest&&f._items.empty());assert(!s.visible&&!s._linkedThread&&!s._graphScene&&s._graphNodes.empty()&&s._graphEdges.empty()&&s._graphCurrentIndex==-1);}
'''
run('world_menu_reset',code)
