"""Actual collision save/restore/remove/revert functions; Havok/actor stand-ins."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/Collision/CollisionHandler.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <mutex>
#include <unordered_map>
#include <vector>
struct Mutex {bool held=false;void lock(){assert(!held);held=true;}void unlock(){assert(held);held=false;}};
namespace RE {
using FormID=uint32_t;using hkHalf=float;
struct hkVector4 {struct {float m128_f32[4]{};}quad;};
enum CHARACTER_FLAGS {kNotPushablePermanent,kPossiblePathObstacle};
struct Flags {template<class...T>void set(T...){}template<class...T>void reset(T...){} };
struct hkpMotion {hkVector4 inertiaAndMassInv;hkHalf gravityFactor=1;void SetMassInv(float f){inertiaAndMassInv.quad.m128_f32[3]=f;} };
struct hkpRigidBody {hkpMotion motion;int refs=0;std::function<void()> released;void* GetCollidableRW(){return this;} };
template<class T>struct hkRefPtr {
 T* ptr=nullptr;hkRefPtr()=default;explicit hkRefPtr(T* p):ptr(p){if(ptr)++ptr->refs;}
 hkRefPtr(const hkRefPtr& p):hkRefPtr(p.ptr){}hkRefPtr(hkRefPtr&& p):ptr(p.ptr){p.ptr=nullptr;}
 ~hkRefPtr(){reset();}void reset(){if(ptr&&--ptr->refs==0&&ptr->released)ptr->released();ptr=nullptr;}
 hkRefPtr& operator=(const hkRefPtr& p){if(this!=&p){reset();ptr=p.ptr;if(ptr)++ptr->refs;}return *this;}
 T* operator->()const{return ptr;}
};
struct hkpCharacterRigidBody {hkpRigidBody* character;};
struct bhkCharacterController {virtual ~bhkCharacterController()=default;int refs=0;std::function<void()> released;Flags flags;struct {hkVector4 surfaceVelocity;}surfaceInfo;};
struct bhkCharRigidBodyController:bhkCharacterController {struct {char pad[16]{};hkpCharacterRigidBody* object=nullptr;}charRigidBody;};
template<class T>using NiPointer=hkRefPtr<T>;
template<class T>struct Ptr {T* p;T* get(){return p;}};
struct Process {Ptr<bhkCharacterController> charController;};
struct Actor {FormID id;Process* process;FormID GetFormID(){return id;}Process* GetMiddleHighProcess(){return process;}};
struct TESForm {static inline Actor* available=nullptr;template<class T>static T* LookupByID(FormID){return available;}};
}
template<class T>T skyrim_cast(RE::bhkCharacterController* c){return dynamic_cast<T>(c);}
void ZeroVector4(RE::hkVector4& v){for(float& f:v.quad.m128_f32)f=0;}
std::unordered_map<int,int> footIKSnapshots,actorFootIKStates,controllerSnapshots,actorControllers;
struct CollisionHandler {
 struct RigidBodyState {RE::hkRefPtr<RE::hkpRigidBody> body;float massInv;RE::hkHalf gravityFactor;};
 static inline std::unordered_map<RE::FormID,RigidBodyState> _rigidBodyStates;
 static inline std::vector<RE::FormID> _cache;
 static inline Mutex _mutex;
 static void DisableRigidBodyPhysics(RE::Actor*);
 static void RestoreSavedPhysics(RE::FormID,RE::hkRefPtr<RE::hkpRigidBody>&);
 static void RemoveActor(RE::FormID);static void Clear();
 static void RestoreControllers(RE::FormID,std::vector<RE::NiPointer<RE::bhkCharacterController>>&){assert(_mutex.held);}
 static void RestoreFootIK(RE::FormID){}static void RestoreRigidBodyPhysics(RE::Actor*){}
};
'''
for sig in ('void CollisionHandler::DisableRigidBodyPhysics(', 'void CollisionHandler::RestoreSavedPhysics(',
            'void CollisionHandler::RemoveActor(', 'void CollisionHandler::Clear('):
    code+=function(source,sig)+'\n'
code+=r'''
int main(){
 RE::hkpRigidBody body;body.motion.SetMassInv(0.125f);body.motion.gravityFactor=0.375f;
 int releases=0;body.released=[&](){assert(!CollisionHandler::_mutex.held);++releases;};
 RE::hkpCharacterRigidBody character{&body};RE::bhkCharRigidBodyController controller;controller.charRigidBody.object=&character;
 RE::Process process{{&controller}};RE::Actor actor{7,&process};
 CollisionHandler::_cache={7};
 {std::unique_lock lock{CollisionHandler::_mutex};CollisionHandler::DisableRigidBodyPhysics(&actor);CollisionHandler::DisableRigidBodyPhysics(&actor);}
 assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==0&&body.motion.gravityFactor==0);
 assert(body.refs==1);RE::TESForm::available=nullptr;
 CollisionHandler::RemoveActor(7);
 assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==0.125f&&body.motion.gravityFactor==0.375f);
 assert(CollisionHandler::_cache.empty()&&CollisionHandler::_rigidBodyStates.empty()&&body.refs==0&&releases==1);
 CollisionHandler::RemoveActor(7);assert(releases==1);
 CollisionHandler::_cache={7};{std::unique_lock lock{CollisionHandler::_mutex};CollisionHandler::DisableRigidBodyPhysics(&actor);}
 CollisionHandler::Clear();assert(body.refs==0&&releases==2&&CollisionHandler::_rigidBodyStates.empty());
 // Revert clears old-world ownership without restoring physics into that world.
 assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==0&&body.motion.gravityFactor==0);
}
'''
run('collision_physics_restore',code)
print('PASS: real collision save/remove/revert restore original mass/gravity, preserve first snapshot and release body after cache unlock')
