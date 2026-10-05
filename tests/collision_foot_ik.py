"""Actual Foot IK ownership and graph/cache lock ordering with graph/Havok stand-ins."""
from source_regressions import ROOT,function,run
source=(ROOT/'src/Thread/Collision/CollisionHandler.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <unordered_map>
#include <vector>
#include <iostream>
namespace std::ranges {template<class R,class T>bool contains(const R& r,const T& v){return std::find(r.begin(),r.end(),v)!=r.end();}}
struct CacheMutex {
 bool held=false,exclusive=false;
 void lock(){assert(!held);held=true;exclusive=true;}void unlock(){assert(held);held=false;exclusive=false;}
 void lock_shared(){lock();exclusive=false;}void unlock_shared(){unlock();}
};
CacheMutex cache;
namespace RE {
 using FormID=unsigned;
 struct hkReferencedObject {void* vtable=nullptr;unsigned refs=0,pad=0;};
 struct Vec4 {float x=0,y=0,z=0,w=0;bool operator==(const Vec4&)const=default;};
 struct hkQuaternion {Vec4 vec;};
 template<class T>struct hkRefPtr {
  T* ptr=nullptr;
  hkRefPtr()=default;explicit hkRefPtr(T* p):ptr(p){if(ptr)++ptr->refs;}
  hkRefPtr(const hkRefPtr& p):hkRefPtr(p.ptr){}hkRefPtr(hkRefPtr&& p):ptr(p.ptr){p.ptr=nullptr;}
  ~hkRefPtr(){if(ptr)--ptr->refs;}
  T* get()const{return ptr;}T* operator->()const{return ptr;}
  hkRefPtr& operator=(const hkRefPtr& p){if(this!=&p){if(ptr)--ptr->refs;ptr=p.ptr;if(ptr)++ptr->refs;}return *this;}
 };
 struct Lock {bool held=false;};
 struct BSSpinLockGuard {Lock& lock;BSSpinLockGuard(Lock& l):lock(l){assert(!cache.held&&!lock.held);lock.held=true;}~BSSpinLockGuard(){assert(!cache.held);lock.held=false;}};
}
'''
a=source.index('        struct hkbFootIkDriver');b=source.index('    }\n\n    void CollisionHandler::Install()',a)
code+=source[a:source.index('        struct ControllerSnapshot',a)] + source[source.index('        // Protected by CollisionHandler::_mutex.',a):b]
code+=r'''
namespace RE {
 struct Graph {ShadowhkbCharacter characterInstance;};
 struct Manager {
  struct {Lock updateLock;} data;
  std::vector<std::shared_ptr<Graph>> graphs;
  auto& GetRuntimeData(){return data;}
 };
 using BSAnimationGraphManagerPtr=std::shared_ptr<Manager>;
 struct hkpRigidBody : hkReferencedObject {};
 struct Controller {int refs=0;};using bhkCharacterController=Controller;template<class T>using NiPointer=hkRefPtr<T>;
 struct Process {struct {Controller* value=nullptr;Controller* get(){return value;}} charController;};
 struct Actor {FormID id;BSAnimationGraphManagerPtr manager;Process* process=nullptr;Process* GetMiddleHighProcess(){return process;}FormID GetFormID(){return id;}bool GetAnimationGraphManager(BSAnimationGraphManagerPtr& out){out=manager;return bool(manager);}};
 struct TESForm {static inline Actor* actor=nullptr;template<class T>static T* LookupByID(FormID id){return actor&&actor->id==id?actor:nullptr;}};
}
std::unordered_map<int,int> controllerSnapshots,actorControllers;
struct CollisionHandler {
 static inline CacheMutex& _mutex=cache;
 static inline std::vector<RE::FormID> _cache;
 static inline std::unordered_map<int,int> _rigidBodyStates;
 static inline int originalMoves=0;
 static void _originalApplyMovementDelta(RE::Actor*,float){assert(!cache.held);++originalMoves;}
 static void CaptureController(RE::FormID,RE::Controller*){assert(cache.held&&cache.exclusive);}
 static void RestoreControllers(RE::FormID,std::vector<RE::NiPointer<RE::bhkCharacterController>>&){assert(cache.held&&cache.exclusive);}
 static void ConfigureControllerForNoCollision(RE::Controller*){assert(cache.held&&cache.exclusive);}
 static void DisableRigidBodyPhysics(RE::Actor*){assert(cache.held&&cache.exclusive);}
 static void RestoreRigidBodyPhysics(RE::Actor*){assert(cache.held&&cache.exclusive);}
 static void RestoreSavedPhysics(RE::FormID,RE::hkRefPtr<RE::hkpRigidBody>&){assert(cache.held&&cache.exclusive);}
 static void AddActor(RE::FormID);static void RemoveActor(RE::FormID);static void Hook_ApplyMovementDelta(RE::Actor*,float);
 static void DisableFootIK(RE::Actor*);static void RestoreFootIK(RE::FormID);static void Clear();
};
'''
# Namespace maps above use the SDK manager alias; declare it before those declarations.
code=code.replace('        struct FootIKSnapshot', 'namespace RE {struct Manager;using BSAnimationGraphManagerPtr=std::shared_ptr<Manager>;}\n        struct FootIKSnapshot')
for sig in ('void CollisionHandler::DisableFootIK(', 'void CollisionHandler::RestoreFootIK(', 'void CollisionHandler::Clear(', 'void CollisionHandler::AddActor(', 'void CollisionHandler::RemoveActor(', 'void CollisionHandler::Hook_ApplyMovementDelta('):code+=function(source,sig)+'\n'
code+=r'''
void remove(unsigned id){std::erase(CollisionHandler::_cache,id);CollisionHandler::RestoreFootIK(id);}
int main(){
 hkbFootIkDriver driver;driver.disableFootIk=true;driver.alignedGroundRotation.vec={.1f,.2f,.3f,.4f};
 auto graph=std::make_shared<RE::Graph>();graph->characterInstance.footIkDriver=RE::hkRefPtr<hkbFootIkDriver>{&driver};
 auto manager=std::make_shared<RE::Manager>();manager->graphs={graph,graph,nullptr};
 RE::Actor first{1,manager},second{2,manager};auto original=driver.alignedGroundRotation.vec;
 CollisionHandler::_cache={1,2};
 CollisionHandler::DisableFootIK(&first);CollisionHandler::DisableFootIK(&first);CollisionHandler::DisableFootIK(&second);
 assert(footIKSnapshots.size()==1&&footIKSnapshots.at(&driver).owners==2&&actorFootIKStates.size()==2);
 assert(driver.disableFootIk&&(driver.alignedGroundRotation.vec==RE::Vec4{0,0,0,1}));
 remove(1);assert(driver.disableFootIk&&(driver.alignedGroundRotation.vec==RE::Vec4{0,0,0,1}));
 // Cached graph ownership permits restore when Actor cannot be looked up.
 first.manager.reset();second.manager.reset();remove(2);
 assert(driver.disableFootIk&&driver.alignedGroundRotation.vec==original&&footIKSnapshots.empty()&&actorFootIKStates.empty());
 driver.disableFootIk=false;first.manager=manager;CollisionHandler::_cache={1};CollisionHandler::DisableFootIK(&first);
 CollisionHandler::RestoreFootIK(1);assert(driver.disableFootIk); // Still registered: a stale removal cannot restore it.
 remove(1);assert(!driver.disableFootIk&&driver.alignedGroundRotation.vec==original);
 CollisionHandler::DisableFootIK(&first);assert(actorFootIKStates.empty()); // Stale add after removal.
 CollisionHandler::_cache={1};CollisionHandler::DisableFootIK(&first);assert(driver.refs==2);
 CollisionHandler::Clear();assert(driver.refs==1&&footIKSnapshots.empty()&&actorFootIKStates.empty());
 assert(driver.disableFootIk&&(driver.alignedGroundRotation.vec==RE::Vec4{0,0,0,1})); // Revert never writes old-world state.
 CollisionHandler::RestoreFootIK(1);assert(driver.refs==1);
 // Exercise real entry points: graph acquisition must occur after the cache lock is released.
 first.manager=manager;RE::TESForm::actor=&first;
 CollisionHandler::AddActor(1);CollisionHandler::AddActor(1);
 assert(actorFootIKStates.size()==1&&footIKSnapshots.at(&driver).owners==1);
 RE::Process process;RE::Controller controller;process.charController.value=&controller;first.process=&process;
 CollisionHandler::Hook_ApplyMovementDelta(&first,0);assert(CollisionHandler::originalMoves==0);
 RE::TESForm::actor=nullptr;CollisionHandler::RemoveActor(1);
 assert(actorFootIKStates.empty()&&footIKSnapshots.empty());
 CollisionHandler::Hook_ApplyMovementDelta(&first,0);assert(CollisionHandler::originalMoves==1);
 std::cout<<"PASS: actual Foot IK preserves original flag/quaternion, deduplicates shared graphs, counts owners and discards Revert state\n";
}
'''
run('collision_foot_ik',code)
