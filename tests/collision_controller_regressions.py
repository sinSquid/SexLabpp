"""Compile extracted collision disable/restore paths with controller stand-ins.

This reproduces the unsafe proxy-to-rigid-body route, not Skyrim's ABI or Havok.
--baseline-ref HEAD verifies that the pre-fix production path fails the cases.
Run from an MSVC developer shell; no Mod linking, packaging or deployment.
"""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()
path = 'src/Thread/Collision/CollisionHandler.cpp'
source = (subprocess.check_output(['git', 'show', args.baseline_ref + ':' + path], cwd=ROOT).decode('utf-8-sig')
          if args.baseline_ref else (ROOT / path).read_text(encoding='utf-8-sig'))


def function(signature):
    start = source.index(signature)
    end, depth = source.index('{', start) + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


code = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
namespace RE {
using FormID = uint32_t;
enum class CHARACTER_FLAGS : uint32_t { kNotPushablePermanent=1, kPossiblePathObstacle=2 };
enum class hkpCharacterStateType { kOnGround, kSwimming };
struct Flags {
 uint32_t bits=2;
 uint32_t underlying()const{return bits;}
 void set(CHARACTER_FLAGS f){bits|=uint32_t(f);}
 void reset(CHARACTER_FLAGS f){bits&=~uint32_t(f);}
 Flags& operator=(CHARACTER_FLAGS f){bits=uint32_t(f);return *this;}
};
template<class T> struct Pointer {
 T* p=nullptr;
 Pointer()=default;
 explicit Pointer(T* v):p(v){}
 T* get()const{return p;}
 void reset(){p=nullptr;}
};
template<class T> using NiPointer=Pointer<T>;
template<class T> using hkRefPtr=Pointer<T>;
struct Vector { float m128_f32[4]{}; };
struct Motion {
 bool valid=true;
 struct {Vector quad;} inertiaAndMassInv;
 float gravityFactor=.3f;
 void SetMassInv(float v){
  if(!valid)throw std::logic_error("proxy phantom used as a rigid body motion");
  inertiaAndMassInv.quad.m128_f32[3]=v;
 }
};
struct hkpRigidBody { Motion motion; void* GetCollidableRW(){return this;} };
struct hkReferencedObject { virtual ~hkReferencedObject()=default; };
struct hkpCharacterRigidBody:hkReferencedObject { hkpRigidBody* character=nullptr; };
struct bhkCharacterController {
 virtual ~bhkCharacterController()=default;
 hkpRigidBody* genericResult=nullptr;
 int genericCalls=0;
 hkpRigidBody* GetRigidBody(){++genericCalls;return genericResult;}
 Flags flags;
 struct {hkpCharacterStateType currentState=hkpCharacterStateType::kOnGround;} context;
 float pitchAngle=.2f,rollAngle=.4f,calculatePitchTimer=8;
 struct {Vector surfaceVelocity;} surfaceInfo;
};
struct bhkCharRigidBodyController:bhkCharacterController {
 struct {Pointer<hkReferencedObject> referencedObject;} charRigidBody;
};
struct bhkCharProxyController:bhkCharacterController {};
struct Process { Pointer<bhkCharacterController> charController; };
struct Actor { FormID id; Process* process; Process* GetMiddleHighProcess(){return process;} FormID GetFormID(){return id;} };
}
template<class T,class U>T skyrim_cast(U* p){return dynamic_cast<T>(p);}
struct PhysicsState {
 RE::NiPointer<RE::bhkCharacterController> controller;
 RE::hkRefPtr<RE::hkpRigidBody> rigidBody;
 uint32_t flags=0;
 RE::hkpCharacterStateType characterState=RE::hkpCharacterStateType::kOnGround;
 float pitchAngle=0,rollAngle=0,calculatePitchTimer=0,massInverse=0,gravityFactor=0;
};
std::unordered_map<RE::FormID,PhysicsState> physicsStates;
constexpr uint32_t kOwnedControllerFlags=3;
void ZeroVector4(RE::Vector& v){v={};}
struct CollisionHandler {
 static void DisableRigidBodyPhysics(RE::Actor*);
 static void RestoreRigidBodyPhysics(RE::Actor*);
};
'''
if 'RE::hkpRigidBody* GetControllerRigidBody(' in source:
    code += function('RE::hkpRigidBody* GetControllerRigidBody(')
code += function('void CollisionHandler::DisableRigidBodyPhysics(')
code += function('void CollisionHandler::RestoreRigidBodyPhysics(')
code += r'''
int main(){
 try {
  RE::hkpRigidBody phantom;
  phantom.motion.valid=false;
  RE::bhkCharProxyController proxy;
  proxy.genericResult=&phantom;
  RE::Process process{RE::Pointer<RE::bhkCharacterController>{&proxy}};
  RE::Actor actor{14,&process};
  CollisionHandler::DisableRigidBodyPhysics(&actor);
  CollisionHandler::RestoreRigidBodyPhysics(&actor);
  assert(proxy.genericCalls==0); // A proxy must never enter the generic rigid-body route.
  assert(proxy.flags.underlying()==2);
  assert(phantom.motion.gravityFactor==.3f);
  RE::bhkCharRigidBodyController rigid;
  process.charController=RE::Pointer<RE::bhkCharacterController>{&rigid};
  CollisionHandler::DisableRigidBodyPhysics(&actor); // Missing Havok wrapper.
  CollisionHandler::RestoreRigidBodyPhysics(&actor);
  RE::hkpCharacterRigidBody wrapper;
  rigid.charRigidBody.referencedObject=RE::Pointer<RE::hkReferencedObject>{&wrapper};
  CollisionHandler::DisableRigidBodyPhysics(&actor); // Missing character body.
  RE::hkpRigidBody body;
  body.motion.inertiaAndMassInv.quad.m128_f32[3]=.02f;
  wrapper.character=&body;
  CollisionHandler::DisableRigidBodyPhysics(&actor);
  CollisionHandler::DisableRigidBodyPhysics(&actor); // Keep the pristine snapshot.
  assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==0);
  assert(body.motion.gravityFactor==0);
  CollisionHandler::RestoreRigidBodyPhysics(&actor);
  assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==.02f);
  assert(body.motion.gravityFactor==.3f);
  body.motion.inertiaAndMassInv.quad.m128_f32[3]=.04f;
  body.motion.gravityFactor=.6f;
  CollisionHandler::RestoreRigidBodyPhysics(&actor); // Keep another owner's edits.
  assert(body.motion.inertiaAndMassInv.quad.m128_f32[3]==.04f && body.motion.gravityFactor==.6f);
  RE::hkpRigidBody replacement;
  replacement.motion.inertiaAndMassInv.quad.m128_f32[3]=.08f;
  wrapper.character=&replacement;
  CollisionHandler::RestoreRigidBodyPhysics(&actor); // Never restore into a replacement body.
  assert(replacement.motion.inertiaAndMassInv.quad.m128_f32[3]==.08f);
  process.charController=RE::Pointer<RE::bhkCharacterController>{&proxy};
  CollisionHandler::RestoreRigidBodyPhysics(&actor); // Or into a replacement controller.
  process.charController.reset();
  CollisionHandler::DisableRigidBodyPhysics(&actor);
  CollisionHandler::RestoreRigidBodyPhysics(&actor);
  actor.process=nullptr;
  CollisionHandler::DisableRigidBodyPhysics(&actor);
  CollisionHandler::RestoreRigidBodyPhysics(&actor);
  assert(rigid.genericCalls==0 && proxy.genericCalls==0);
  std::cout<<"PASS: proxy, rigid body, missing body, repeated disable, replacement and restore ownership\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
'''
with tempfile.TemporaryDirectory(prefix='collision-controller-') as tmp:
    cpp, exe = Path(tmp) / 'collision.cpp', Path(tmp) / 'collision.exe'
    cpp.write_text(code, encoding='utf-8')
    result = subprocess.run([os.environ.get('CXX', 'cl'), '/nologo', '/std:c++20', '/EHsc', '/W4', '/WX', str(cpp), '/Fe:' + str(exe)],
                            cwd=tmp, capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)
    result = subprocess.run([str(exe)], cwd=tmp, capture_output=True, text=True)
    print(result.stdout + result.stderr, end='')
    raise SystemExit(result.returncode)
