"""Actual controller snapshot helpers, ownership and clear with reference stand-ins."""
from source_regressions import ROOT, function, run
s=(ROOT/'src/Thread/Collision/CollisionHandler.cpp').read_text()
state=s[s.index('        struct ControllerSnapshot'):s.index('        // Protected by CollisionHandler::_mutex.')]
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <unordered_map>
#include <vector>
namespace std::ranges {template<class R,class T>bool contains(const R& r,const T& t){return std::find(r.begin(),r.end(),t)!=r.end();}}
struct Mutex{bool held=false;void lock(){assert(!held);held=true;}void unlock(){held=false;}};
namespace RE {
using FormID=uint32_t;
enum class CHARACTER_FLAGS:uint32_t{kNoGravityOnGround=2,kNoSim=1u<<17,kNotPushablePermanent=1u<<28,kPossiblePathObstacle=1u<<29};
struct Flags{uint32_t value=0;bool any(CHARACTER_FLAGS f){return value&uint32_t(f);}void set(CHARACTER_FLAGS f){value|=uint32_t(f);}void reset(CHARACTER_FLAGS f){value&=~uint32_t(f);}};
struct bhkCharacterController{Flags flags;int refs=0;std::function<void()> released;};
template<class T>struct NiPointer {
 T* p=nullptr;NiPointer()=default;explicit NiPointer(T* a):p(a){if(p)++p->refs;}
 NiPointer(const NiPointer& a):NiPointer(a.p){}NiPointer(NiPointer&& a):p(a.p){a.p=nullptr;}
 ~NiPointer(){if(p&&--p->refs==0&&p->released)p->released();}
};
}
std::unordered_map<int,int> footIKSnapshots,actorFootIKStates;
struct CollisionHandler{
 static inline Mutex _mutex;static inline std::vector<RE::FormID> _cache;
 static inline std::unordered_map<int,int> _rigidBodyStates;
 static void CaptureController(RE::FormID,RE::bhkCharacterController*);
 static void RestoreControllers(RE::FormID,std::vector<RE::NiPointer<RE::bhkCharacterController>>&);
 static void Clear();
};
'''+state+function(s,'void CollisionHandler::CaptureController(')+function(s,'void CollisionHandler::RestoreControllers(')+function(s,'void CollisionHandler::Clear(')+r'''
int main(){
 const uint32_t mask=2|(1u<<17)|(1u<<28)|(1u<<29),other=1u<<7;
 for(unsigned pattern=0;pattern<16;++pattern){
  RE::bhkCharacterController first,second;uint32_t original=other;
  for(unsigned i=0;i<4;++i)if(pattern&(1u<<i))original|=uint32_t(controllerFlags[i]);
  first.flags.value=original;second.flags.value=mask;int released=0;
  first.released=second.released=[&](){assert(!CollisionHandler::_mutex.held);++released;};
  {std::unique_lock lock{CollisionHandler::_mutex};
   CollisionHandler::CaptureController(1,&first);first.flags.value^=mask;
   CollisionHandler::CaptureController(1,&first);CollisionHandler::CaptureController(2,&first);
   CollisionHandler::CaptureController(1,&second);second.flags.value=other;
  }
  assert(first.refs==1&&second.refs==1&&actorControllers[1].size()==2);
  {std::vector<RE::NiPointer<RE::bhkCharacterController>> refs;
   {std::unique_lock lock{CollisionHandler::_mutex};CollisionHandler::RestoreControllers(1,refs);}
   assert(first.flags.value==(original^mask)&&second.flags.value==(mask|other));
  }
  assert(released==1&&first.refs==1);
  {std::vector<RE::NiPointer<RE::bhkCharacterController>> refs;
   {std::unique_lock lock{CollisionHandler::_mutex};CollisionHandler::RestoreControllers(2,refs);CollisionHandler::RestoreControllers(2,refs);}
   assert(first.flags.value==original);
  }
  assert(released==2&&controllerSnapshots.empty()&&actorControllers.empty());
  {std::unique_lock lock{CollisionHandler::_mutex};CollisionHandler::CaptureController(1,&first);first.flags.value^=mask;}
  CollisionHandler::Clear();assert(first.flags.value==(original^mask)&&released==3&&first.refs==0);
 }
}
'''
run('collision_controller_restore',code)
print('PASS: actual controller helpers preserve all 16 original flag combinations, shared/replacement ownership, unrelated bits and Revert without stale writes')
