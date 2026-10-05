"""Actual NiInstance constructor; count state-vector allocations with actor/scene stand-ins."""
import os
import subprocess
from source_regressions import ROOT, function, run

path='src/Thread/NiNode/NiInstance.cpp'
source=(subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
        if os.getenv('REVIEW_BASE') else (ROOT/path).read_text())
code=r'''
#include <cassert>
#include <cstdint>
#include <limits>
#include <memory>
#include <utility>
#include <vector>
template<class T> struct CountAllocator {
 using value_type=T;
 static inline int allocations=0;
 CountAllocator()=default;
 template<class U> CountAllocator(const CountAllocator<U>&){}
 T* allocate(size_t n){++allocations;return std::allocator<T>{}.allocate(n);}
 void deallocate(T* p,size_t n){std::allocator<T>{}.deallocate(p,n);}
 template<class U>bool operator==(const CountAllocator<U>&)const{return true;}
};
namespace RE {struct Actor{};}
namespace Registry {
 struct Scene {
  struct Sex {int get()const{return 0;}};
  struct Data {Sex GetSex()const{return {};}};
  struct Position {Data data;};
  const Position* GetNthPosition(size_t)const{static Position p;return &p;}
 };
}
namespace Thread::NiNode {
 struct NiActor {NiActor(RE::Actor*,int){}};
 struct NiInstance {
  struct PairInteractionState {};
  using StateEntry=std::pair<std::pair<int8_t,int8_t>,PairInteractionState>;
  std::vector<NiActor> positions;
  std::vector<StateEntry,CountAllocator<StateEntry>> states;
  NiInstance(const std::vector<RE::Actor*>&,const Registry::Scene*);
 };
''' + function(source,'NiInstance::NiInstance(') + r'''
}
int main() {
 using Thread::NiNode::NiInstance;
 Registry::Scene scene;RE::Actor actor;
 for(size_t n=0;n<=5;++n) {
  CountAllocator<NiInstance::StateEntry>::allocations=0;
  NiInstance instance(std::vector<RE::Actor*>(n,&actor),&scene);
  assert(instance.states.size()==n*n);
  assert(CountAllocator<NiInstance::StateEntry>::allocations==(n?1:0));
  for(size_t i=0;i<n;++i)for(size_t j=0;j<n;++j) {
   const auto pair=instance.states[i*n+j].first;
   assert(pair.first==i&&pair.second==j);
  }
 }
}
'''
run('interaction_state_capacity',code)
print('PASS: actual constructor preserves every ordered/self pair and allocates state-vector storage once for 1–5 actors')
