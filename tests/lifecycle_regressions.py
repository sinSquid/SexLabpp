"""Exercise actual DestroyInstance with stand-ins for the engine registries."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/Thread.cpp').read_text()
code=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <functional>
#include <iostream>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <shared_mutex>
#include <vector>
#include "Util/SharedSnapshot.h"
namespace RE {
 struct TESQuest{unsigned id;unsigned GetFormID()const{return id;}};
 struct PlayerCharacter{static PlayerCharacter* GetSingleton(){return nullptr;}};
}
namespace SKSE {
 struct Tasks{void AddTask(std::function<void()> task){task();}};
 Tasks* GetTaskInterface(){static Tasks tasks;return &tasks;}
}
namespace Thread {
namespace LegacyNiNode {using NiInstance=int;struct NiUpdate{static inline std::set<unsigned> entries;static void Unregister(unsigned id){entries.erase(id);}};}
namespace NiNode {using NiInstance=int;struct NiUpdate{static inline std::set<unsigned> entries;static void Unregister(unsigned id){entries.erase(id);}};}
namespace Hooks {void SetWeaponDrawBlocked(bool){}}
namespace Interface {struct FurnSelectMenu{static FurnSelectMenu& GetSingleton(){static FurnSelectMenu value;return value;}void Cancel(RE::TESQuest*,int){}};}
struct Instance {
 RE::TESQuest* linkedQst=nullptr;int startupRequest=1;
 std::shared_ptr<std::atomic_bool> creationCancelled=std::make_shared<std::atomic_bool>(false);
 Util::SharedSnapshot<int> niInstance{std::make_shared<int>(1)},niInstanceLegacy{std::make_shared<int>(2)};
 bool released=false;
 void* GetPosition(RE::PlayerCharacter*){return nullptr;}
 void ReleaseAnimations(){released=true;}
 static inline int restored=0;
 static void RestorePreparedActors(RE::TESQuest*){++restored;}
 static inline std::shared_mutex _mInstances;
 static inline std::map<RE::TESQuest*,std::shared_ptr<std::atomic_bool>> creatingInstances;
 static inline std::vector<std::shared_ptr<Instance>> instances,pendingInstances;
 static uint64_t GetWorldGeneration(){return 0;}
 static void DestroyInstance(RE::TESQuest*,bool);
};
'''+function(source,'void Instance::DestroyInstance')+r'''
}
int main(){using namespace Thread;RE::TESQuest owner{1},other{2};
 for(bool preserve:{false,true}){
  auto old=std::make_shared<Instance>();old->linkedQst=&owner;
  auto alive=std::make_shared<Instance>();alive->linkedQst=&other;
  auto pending=std::make_shared<Instance>();pending->linkedQst=&owner;
  auto cancellation=std::make_shared<std::atomic_bool>(false);
  Instance::instances={old,alive};Instance::pendingInstances={pending};Instance::creatingInstances[&owner]=cancellation;
  LegacyNiNode::NiUpdate::entries={1,2};NiNode::NiUpdate::entries={1,2};
  auto retained=old->niInstance.load();
  int before=Instance::restored;
  Instance::DestroyInstance(&owner,preserve);
  assert(*retained==1);
  assert(old->creationCancelled->load() && pending->creationCancelled->load() && cancellation->load());
  assert(Instance::instances.size()==1 && Instance::instances[0]==alive && Instance::pendingInstances.empty());
  assert(!old->niInstance.load() && !old->niInstanceLegacy.load() && old->released);
  assert(!LegacyNiNode::NiUpdate::entries.contains(1) && !NiNode::NiUpdate::entries.contains(1));
  assert(LegacyNiNode::NiUpdate::entries.contains(2) && NiNode::NiUpdate::entries.contains(2));
  assert(Instance::restored==before+!preserve);
  Instance::DestroyInstance(&owner,preserve); // idempotent registry cleanup
 }
 std::cout<<"PASS: production destruction clears both registries, pending creation and quick-reset ownership\n";
}
'''
run('lifecycle',code)
