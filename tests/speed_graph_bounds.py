from statistics_roundtrip import ROOT, function, run
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <memory>
#include <utility>
#include <vector>
namespace logger {template<class... T>void warn(T&&...) {}}
namespace RE {
 struct Node {virtual ~Node()=default;};
 struct Control {float playbackSpeed=1;};
 struct hkbClipGenerator:Node {float playbackSpeed=1;Control* animationControl=nullptr;};
 struct BSSynchronizedClipGenerator:Node {hkbClipGenerator* clipGenerator=nullptr;};
 struct hkbNodeInfo {Node* nodeClone;};
 template<class T>using hkArray=std::vector<T>;
 struct Behavior {hkArray<hkbNodeInfo>* activeNodes=nullptr;};
 struct BShkbAnimationGraph {Behavior* behaviorGraph=nullptr;};
 struct Manager {
  struct Runtime {unsigned activeGraph=0;int updateLock=0;} runtime;
  std::vector<std::shared_ptr<BShkbAnimationGraph>> graphs;
  Runtime& GetRuntimeData(){return runtime;}
 };
 using BSAnimationGraphManagerPtr=std::shared_ptr<Manager>;
 struct Actor {BSAnimationGraphManagerPtr graph;bool GetAnimationGraphManager(BSAnimationGraphManagerPtr& out)const{out=graph;return bool(out);}};
 struct BSSpinLockGuard {int& lock; explicit BSSpinLockGuard(int& value):lock(value){assert(lock==0);lock=1;} ~BSSpinLockGuard(){lock=0;}};
}
template<class T,class U>T skyrim_cast(U* value){return dynamic_cast<T>(value);}
struct Position {struct Data {RE::Actor* actor;RE::Actor* GetActor(){return actor;}} data;};
struct Instance {
 float animationPlaybackSpeed=1.25f;
 std::vector<Position> positions;
 struct Pending {bool playbackHeld;const RE::hkbClipGenerator* observedGenerator;};
 std::vector<Pending> pendingAnimations;
 void SetAnimationPlaybackSpeed(float);
};
'''
code+=function((ROOT/'src/Thread/ThreadAnimation.cpp').read_text(),'void Instance::SetAnimationPlaybackSpeed(')
code+=r'''
int main(){
 Instance instance;RE::Actor actor{std::make_shared<RE::Manager>()};instance.positions.push_back({{&actor}});
 instance.SetAnimationPlaybackSpeed(2);assert(instance.animationPlaybackSpeed==2);
 instance.SetAnimationPlaybackSpeed(std::numeric_limits<float>::quiet_NaN());assert(instance.animationPlaybackSpeed==2);
 instance.SetAnimationPlaybackSpeed(std::numeric_limits<float>::infinity());assert(instance.animationPlaybackSpeed==2);
 RE::hkbClipGenerator clip;RE::Control control;clip.animationControl=&control;
 RE::hkArray<RE::hkbNodeInfo> nodes{{&clip}};RE::Behavior behavior{&nodes};
 auto graph=std::make_shared<RE::BShkbAnimationGraph>();graph->behaviorGraph=&behavior;actor.graph->graphs.push_back(graph);
 actor.graph->runtime.activeGraph=20;instance.SetAnimationPlaybackSpeed(3);assert(clip.playbackSpeed==1);
 actor.graph->runtime.activeGraph=0;instance.SetAnimationPlaybackSpeed(0.5f);assert(clip.playbackSpeed==0.5f&&control.playbackSpeed==0.5f);
 instance.pendingAnimations.push_back({true,&clip});instance.SetAnimationPlaybackSpeed(1);assert(clip.playbackSpeed==0&&control.playbackSpeed==0);
 instance.pendingAnimations.clear();
 RE::BSSynchronizedClipGenerator wrapper; wrapper.clipGenerator=&clip;
 nodes={{&wrapper},{nullptr}};
 instance.positions.push_back({{&actor}});
 instance.SetAnimationPlaybackSpeed(2.5f);assert(clip.playbackSpeed==2.5f&&control.playbackSpeed==2.5f);
 wrapper.clipGenerator=nullptr;instance.SetAnimationPlaybackSpeed(1.5f);assert(clip.playbackSpeed==2.5f);
}
'''
if __name__=='__main__':run('speed_graph_bounds',code)
