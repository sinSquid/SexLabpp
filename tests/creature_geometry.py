"""Compile production node discovery/readiness code with small engine stand-ins.

Checks mixed human/creature scenes and unloaded 3D; does not emulate Skyrim meshes.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'src/Thread/Interaction/NiSurface'
geometry = (BASE / 'ActorGeometry.cpp').read_text(encoding='utf-8')
manager = (BASE / 'CollisionManager.cpp').read_text(encoding='utf-8')
actor_state = (BASE / 'ActorState.cpp').read_text(encoding='utf-8')
crotch_detection = actor_state[actor_state.index('    bool ActorState::Frame::DetectShaftCrotch('):actor_state.index('    bool ActorState::Frame::DetectShaftHand(')]
crotch_detection = crotch_detection.replace('ActorState::Frame::', 'Frame::')
discovery = geometry[geometry.index('        const auto getNode ='):geometry.index('        getNode(HEAD,')]
shaft_discovery = geometry[geometry.index('        for (const auto& base : SHAFT_BASES)'):geometry.index('        logger::info("NiSurface Interaction: Shaft discovery')]
shaft_names = re.findall(r'ShaftBase\{ "([^"]+)"', geometry)
crotch = geometry[geometry.index('    std::optional<GeometryMath::Segment> ActorGeometry::GetCrotchSegment()'):]
crotch = crotch[:crotch.index('\n    }') + len('\n    }')]
readiness = manager[manager.index('        bool geometryChanged ='):manager.index('        std::vector<ActorState::Frame> frames;')]
readiness = readiness.replace('return;', 'return false;')

code = r'''
#include <cassert>
#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <tuple>
#include <vector>
namespace logger { template<class... T> void info(T...) {} }
namespace RE {
struct NiPoint3 {
    float x=0, y=0, z=0;
    NiPoint3 operator-(NiPoint3 b) const { return {x-b.x,y-b.y,z-b.z}; }
    float Length() const { return std::sqrt(x*x+y*y+z*z); }
};
struct NiNode {
    struct { NiPoint3 translate; } world;
    std::map<std::string_view, NiNode*> nodes;
    NiNode* GetObjectByName(std::string_view n) { auto it=nodes.find(n); return it==nodes.end()?nullptr:it->second; }
    NiNode* AsNode() { return this; }
};
template<class T> struct NiPointer {
    T* value=nullptr;
    NiPointer()=default;
    NiPointer(T* p):value(p){}
    T* get() const { return value; }
    T* operator->() const { return value; }
    explicit operator bool() const { return value!=nullptr; }
};
struct Actor { NiNode* root; NiNode* Get3D() { return root; } int GetFormID() { return 1; } };
}
namespace GeometryMath {
struct Segment { RE::NiPoint3 start,end; RE::NiPoint3 Vector() const { return end-start; } float Length() const { return Vector().Length(); } };
inline float angle=0;
float GetAngleDegree(RE::NiPoint3,RE::NiPoint3) { return angle; }
Segment ClosestSegmentBetweenSegments(Segment,Segment) { return {}; }
}
constexpr std::string_view PELVIS="NPC Pelvis [Pelv]", LOWER_SPINE="NPC Spine [Spn0]";
struct ActorGeometry {
    RE::NiPointer<RE::NiNode> pelvis, lowerSpine;
    struct Shaft {
        Shaft(RE::Actor*, RE::NiPointer<RE::NiNode>, int) {}
    };
    std::vector<Shaft> shafts;
    std::optional<GeometryMath::Segment> GetCrotchSegment() const;
    void Discover(RE::NiNode* obj) {
        RE::Actor actor{obj};
        const auto a_actor=&actor;
        const auto racestr="test";
'''+discovery+r'''
        struct ShaftBase { std::string_view name; int rotation=0; };
        const ShaftBase SHAFT_BASES[]{
'''+',\n'.join('            {"' + name + '"}' for name in shaft_names)+r'''
        };
'''+shaft_discovery+r'''
    }
};
'''+crotch+r'''
struct Position {
    RE::Actor* actor;
    RE::NiPointer<RE::NiNode> root;
    ActorGeometry geometry;
    std::vector<int> interactions{1}, motionStates{1};
    void ResetGeometry(RE::NiNode* next) {
        root=RE::NiPointer{next}; geometry={};
        if(next) geometry.Discover(next);
    }
};
bool Ready(std::vector<Position>& positions) {
'''+readiness+r'''
    return true;
}
struct Opening { float distance; RE::NiPoint3 axis{},deep{},center{}; };
template<class T> float DistanceToOpening(const T&, Opening opening) { return opening.distance; }
struct Interaction {
    enum class Action { Vaginal=1,Anal=2,Grinding=3 };
    int partner; Action action;
    Interaction(int p,Action a,float,RE::NiPoint3):partner(p),action(a){}
};
namespace Settings {
constexpr float fPenetrationVaginalToleranceRepeat=1, fPenetrationAnalToleranceRepeat=1, fPenetrationVaginalTolerance=0;
constexpr float fDistanceCrotch=5,fAnglePenetration=30,fAngleGrinding=5,fAdjustSchlongVaginalLimit=30;
}
// Checked access makes an absent optional deterministic instead of relying on release-build UB.
template<class T> struct CheckedOptional:std::optional<T> {
    using std::optional<T>::optional;
    using std::optional<T>::operator=;
    T* operator->() { return &this->value(); }
    const T* operator->() const { return &this->value(); }
};
struct ShaftShape {};
RE::NiPoint3 GetShaftTipDirection(const ShaftShape&) { return {}; }
bool rotationAllowed=true;
bool RotateNode(RE::NiNode*,GeometryMath::Segment,RE::NiPoint3,float) { return rotationAllowed; }
namespace Geometry { struct Shaft {
    RE::NiNode* base=nullptr;
    GeometryMath::Segment GetReferenceSegment() const { return {{0,0,0},{0,1,0}}; }
    RE::NiNode* GetBaseReferenceNode() const { return base; }
    const ShaftShape* GetCollisionShape() const { return nullptr; }
}; }
struct Frame {
    struct { int actor=1; ActorGeometry geometry; std::vector<Interaction> interactions; } state;
    CheckedOptional<Opening> vaginalOpening,analOpening;
    std::vector<Interaction> interactions;
    bool DetectShaftCrotch(const Frame&,const Geometry::Shaft&);
};
'''+crotch_detection+r'''
void CheckSingleOpening(bool vaginal) {
    Frame target,partner;
    if(vaginal) target.vaginalOpening=Opening{1}; else target.analOpening=Opening{1};
    Geometry::Shaft shaft;
    GeometryMath::angle=0;
    assert(target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.back().action==(vaginal?Interaction::Action::Vaginal:Interaction::Action::Anal));
    target.interactions.clear();
    GeometryMath::angle=90;
    assert(!target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.empty());
    GeometryMath::angle=0;
    RE::NiNode base;
    shaft.base=&base;
    rotationAllowed=false;
    assert(!target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.empty());
    rotationAllowed=true;
    if(vaginal) target.vaginalOpening=Opening{20}; else target.analOpening=Opening{20};
    assert(!target.DetectShaftCrotch(partner,shaft));
}
int main() try {
    CheckSingleOpening(true);
    CheckSingleOpening(false);
    Frame target,partner;
    target.vaginalOpening=Opening{1}; target.analOpening=Opening{5};
    Geometry::Shaft shaft;
    GeometryMath::angle=0;
    assert(target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.back().action==Interaction::Action::Vaginal);
    target.vaginalOpening=Opening{5}; target.analOpening=Opening{1};
    assert(target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.back().action==Interaction::Action::Anal);
    GeometryMath::angle=180;
    assert(target.DetectShaftCrotch(partner,shaft));
    assert(target.interactions.back().action==Interaction::Action::Grinding);
    RE::NiNode pelvis,spine,humanRoot,horseRoot,horseShaft;
    horseRoot.nodes["HS 3"]=&horseShaft;
    pelvis.world.translate={1,2,3}; spine.world.translate={4,5,6};
    humanRoot.nodes[PELVIS]=&pelvis; humanRoot.nodes[LOWER_SPINE]=&spine;
    ActorGeometry human, horse;
    human.Discover(&humanRoot); horse.Discover(&horseRoot);
    assert(horse.shafts.size()==1); // Production discovery still reaches the MNC horse base.
    auto segment=human.GetCrotchSegment();
    assert(segment && segment->start.x==4 && segment->end.x==1);
    assert(!horse.GetCrotchSegment());
    horse.pelvis=RE::NiPointer{&pelvis};
    assert(!horse.GetCrotchSegment());
    RE::Actor a{&humanRoot}, b{&horseRoot};
    std::vector<Position> scene{{&a,RE::NiPointer{&humanRoot},human},{&b,RE::NiPointer{&horseRoot},horse}};
    assert(Ready(scene)); // A creature cannot disable the human's collision detection.
    b.root=nullptr;
    assert(!Ready(scene));
    for(auto& p:scene) assert(p.interactions.empty() && p.motionStates.empty());
    b.root=&horseRoot;
    assert(Ready(scene)); // A replacement lacking human bones can rejoin safely.
    assert(!scene[1].geometry.GetCrotchSegment());
    assert(scene[1].geometry.shafts.size()==1);
}
catch(const std::bad_optional_access&) { return 42; }
'''

def run_cpp(source):
    with tempfile.TemporaryDirectory(prefix='sexlab-creature-') as tmp:
        path = Path(tmp)
        cpp, binary = path / 'geometry.cpp', path / 'geometry.exe'
        cpp.write_text(source, encoding='utf-8')
        compiler = os.environ.get('CXX') or shutil.which('g++')
        if compiler:
            subprocess.run([compiler, '-std=c++20', str(cpp), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
        else:
            vswhere = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
            installation = subprocess.check_output([str(vswhere), '-latest', '-products', '*', '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
            assert installation, 'A C++ compiler is required (CXX/g++ or Visual Studio Build Tools)'
            vcvars = Path(installation) / 'VC/Auxiliary/Build/vcvars64.bat'
            command = f'call "{vcvars}" >nul && cl /nologo /std:c++20 /EHsc "{cpp}" /Fe:"{binary}" && "{binary}"'
            subprocess.run(command, shell=True, cwd=tmp, check=True)


if __name__ == '__main__':
    run_cpp(code)
    print('PASS: complete crotch detector success/angle/rotation/distance paths, horse shafts, mixed scene and unload')
