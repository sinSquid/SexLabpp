"""Actual ReleaseAnimations with graph/lock stand-ins; no Havok ABI claim."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/ThreadAnimation.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>
namespace RE {
struct BSSpinLock {bool held=false;};
inline std::vector<BSSpinLock*> acquired;
struct BSSpinLockGuard {BSSpinLock& lock; BSSpinLockGuard(BSSpinLock& l):lock(l){
 if(l.held)throw std::runtime_error("duplicate lock");
 if(!acquired.empty()&&!std::less<BSSpinLock*>{}(acquired.back(),&l))throw std::runtime_error("unordered locks");
 l.held=true;acquired.push_back(&l);}
 ~BSSpinLockGuard(){lock.held=false;}};
struct Base {virtual ~Base()=default;};
struct Control {float localTime=0,playbackSpeed=0;};
struct hkbClipGenerator:Base {float localTime=0,startTime=5,time=0,playbackSpeed=0;Control* animationControl=nullptr;std::string name="clip";};
struct BSSynchronizedClipGenerator:Base {hkbClipGenerator* clipGenerator=nullptr;};
struct Active {Base* nodeClone;};
struct Behavior {std::vector<Active>* activeNodes;};
struct Graph {Behavior* behaviorGraph;};
struct Manager {struct Runtime {size_t activeGraph=0;BSSpinLock updateLock;} runtime;std::vector<std::shared_ptr<Graph>> graphs;Runtime& GetRuntimeData(){return runtime;}};
using BSAnimationGraphManagerPtr=std::shared_ptr<Manager>;
struct Actor {BSAnimationGraphManagerPtr manager;bool GetAnimationGraphManager(BSAnimationGraphManagerPtr& out){out=manager;return bool(out);}};
}
template<class T> T skyrim_cast(RE::Base* p){return dynamic_cast<T>(p);}
std::string GetClipAnimationName(RE::hkbClipGenerator* c){return c->name;}
struct Pending {bool playbackHeld;RE::Actor* actor;RE::hkbClipGenerator* observedGenerator;std::string observedAnimation;};
struct Instance {std::vector<Pending> pendingAnimations;float animationPlaybackSpeed=2;void ReleaseAnimations();};
'''+function(source,'void Instance::ReleaseAnimations()')+r'''
int main(){
 RE::hkbClipGenerator clip;RE::Control control;clip.animationControl=&control;
 std::vector<RE::Active> nodes{{&clip}};RE::Behavior behavior{&nodes};
 auto a=std::make_shared<RE::Manager>(),b=std::make_shared<RE::Manager>();
 a->graphs.push_back(std::make_shared<RE::Graph>(RE::Graph{&behavior}));b->graphs=a->graphs;
 RE::Actor first{a},shared{a},second{b},missing{};
 for(bool reverse:{false,true}){
  Instance instance{{{true,&first,&clip,"clip"},{true,&shared,&clip,"clip"},{true,&second,&clip,"clip"},{true,&missing,&clip,"clip"},{false,&first,&clip,"clip"}}};
  if(reverse)std::reverse(instance.pendingAnimations.begin(),instance.pendingAnimations.end());
  RE::acquired.clear();instance.ReleaseAnimations();assert(RE::acquired.size()==2);
  assert(!a->runtime.updateLock.held&&!b->runtime.updateLock.held);
  assert(clip.localTime==5&&clip.time==5&&clip.playbackSpeed==2&&control.playbackSpeed==2);
 }
 a->runtime.activeGraph=10;RE::acquired.clear();Instance{{{true,&first,&clip,"clip"}}}.ReleaseAnimations();
}
'''
run('animation_graph_locks',code)
print('PASS: actual ReleaseAnimations deduplicates shared managers, orders locks independently of actors and releases clips')
