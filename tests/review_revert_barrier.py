"""Regression for real restore-wrapper and Revert serialization; engine effects are stand-ins."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def function(source, signature):
    start=source.index(signature);brace=source.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

animation=(ROOT/'src/Thread/ThreadAnimation.cpp').read_text()
thread=(ROOT/'src/Thread/Thread.cpp').read_text()
code=r'''
#include <atomic>
#include <cassert>
#include <condition_variable>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <future>
#include <map>
#include <memory>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <vector>
std::mutex pauseMutex;std::condition_variable pauseCv;bool reached=false,resume=false;
std::atomic<bool> reverted=false;std::atomic<int> lateWrites=0;
namespace RE {
using FormID=unsigned;struct TESQuest {unsigned GetFormID(){return 1;}};
enum class ACTOR_LIFE_STATE{kUnconcious,kAlive};enum class ActorValue{kVariable05};
struct Actor {
 struct State {struct {ACTOR_LIFE_STATE lifeState=ACTOR_LIFE_STATE::kAlive;} actorState1;} state;
 bool first=true;
 bool IsPlayerRef(){
  if(first){first=false;std::unique_lock lock(pauseMutex);reached=true;pauseCv.notify_all();pauseCv.wait(lock,[]{return resume;});}
  return false;
 }
 void SetGraphVariableInt(const char*,int){if(reverted)++lateWrites;}
 void SetGraphVariableBool(const char*,bool){if(reverted)++lateWrites;}
 State* AsActorState(){return &state;}
 Actor* AsActorValueOwner(){return this;}
 void SetActorValue(ActorValue,float){if(reverted)++lateWrites;}
};
}
namespace Registry {struct Scale {static Scale* GetSingleton(){static Scale s;return &s;}void RemoveScale(RE::Actor*){}};}
namespace logger {template<class...T>void info(T&&...){};}
namespace Thread {
namespace Hooks {void SetWeaponDrawBlocked(bool){}}
namespace Interface {struct SceneHUD {static SceneHUD& GetSingleton(){static SceneHUD h;return h;}void SetSpeedControl(RE::TESQuest*,bool){}void Destroy(){}};}
namespace Interaction::NiSurface {struct Manager {static void Clear(){}};}
struct ActorPreparation {
 RE::TESQuest* owner;RE::Actor* actor;RE::ACTOR_LIFE_STATE lifeState;
 int isNPC=1;bool humanoidFootIKDisabled=false,hasIsNPC=true,hasHumanoidFootIKDisabled=true;
};
std::mutex actorPreparationLock;std::unordered_map<RE::FormID,ActorPreparation> actorPreparations;
struct Instance {
 RE::TESQuest* linkedQst=nullptr;
 static inline std::recursive_mutex _mInstances;
 static inline std::vector<std::unique_ptr<Instance>> instances;
 static void CancelPendingCreations(){}
 static void RestorePreparedActors(RE::TESQuest*);static void DiscardPreparedActors();static void RevertInstances();
};
'''
code+=function(animation,'void RestorePreparedActorState(')
code+=function(animation,'void Instance::RestorePreparedActors(')
code+=function(animation,'void Instance::DiscardPreparedActors()')
code+=function(thread,'void Instance::RevertInstances()')
code+=r'''
}
int main(){
 RE::TESQuest quest;RE::Actor actor;
 Thread::actorPreparations.emplace(10,Thread::ActorPreparation{&quest,&actor,RE::ACTOR_LIFE_STATE::kUnconcious});
 std::thread restoring([&]{Thread::Instance::RestorePreparedActors(&quest);});
 {std::unique_lock lock(pauseMutex);pauseCv.wait(lock,[]{return reached;});}
 std::atomic<bool> revertEntered=false;
 auto reverting=std::async(std::launch::async,[&]{revertEntered=true;Thread::Instance::RevertInstances();reverted=true;});
 while(!revertEntered.load())std::this_thread::yield();
 const bool waited=reverting.wait_for(std::chrono::milliseconds(20))==std::future_status::timeout;
 {std::unique_lock lock(pauseMutex);resume=true;}pauseCv.notify_all();restoring.join();
 reverting.get();
 std::cout<<"writes to captured old actor after Revert returns: "<<lateWrites<<std::endl;
 assert(waited&&lateWrites==0);
 // A restore call arriving after Revert cannot recover a discarded entry.
 Thread::Instance::RestorePreparedActors(&quest);assert(lateWrites==0);
 std::cout<<"PASS: actual restore wrapper and Revert serialize old-world writes and reject late restoration"<<std::endl;
}
'''
with tempfile.TemporaryDirectory(prefix='slpp-independent-revert-') as temp:
    cpp=Path(temp)/'probe.cpp';binary=Path(temp)/'probe'
    cpp.write_text(code)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++23','-pthread',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=10)
