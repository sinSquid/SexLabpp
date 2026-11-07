"""Run the production interaction queries with geometry/engine stand-ins.

Exercises capability fallback through flags, predicates, partner and string queries.
--baseline-ref HEAD demonstrates the registered-scene fallback regression.
"""
import argparse
from pathlib import Path
import subprocess
from creature_geometry import run_cpp

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--baseline-ref')
args = parser.parse_args()
path = 'src/Thread/Interaction/Interaction.cpp'
source = (subprocess.check_output(['git', 'show', f'{args.baseline_ref}:{path}'], cwd=ROOT).decode('utf-8')
          if args.baseline_ref else (ROOT / path).read_text(encoding='utf-8'))
source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
header = (ROOT / 'src/Thread/Interaction/Interaction.h').read_text(encoding='utf-8').replace('#pragma once', '')

code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <functional>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>
#undef assert
#define assert(condition) do { if (!(condition)) { std::cerr << "FAIL: " << #condition << '\n'; std::exit(42); } } while(false)
namespace logger { template<class... T> void warn(T...) {} template<class... T> void info(T...) {} }
namespace RE {
using FormID=uint32_t;
using BSFixedString=std::string;
struct Node {};
struct Actor { uint32_t formID; Node* root; Node* Get3D() const { return root; } };
template<class T> struct Ptr {
    T* value=nullptr;
    T* get() const { return value; }
    T* operator->() const { return value; }
    explicit operator bool() const { return value; }
};
}
namespace Registry { enum class Sex { Female }; }
namespace Thread::Interaction::NiSurface {
struct Geometry {
    RE::Node *head=nullptr,*leftHand=nullptr,*rightHand=nullptr,*leftThumb=nullptr,*rightThumb=nullptr;
    RE::Node *leftFoot=nullptr,*rightFoot=nullptr,*leftToe=nullptr,*rightToe=nullptr;
    RE::Node *animObjectA=nullptr,*animObjectB=nullptr,*animObjectLeft=nullptr,*animObjectRight=nullptr;
    std::vector<int> shafts;
    bool vaginal=false,anal=false,crotch=false;
    std::optional<int> GetVaginalSegment() const { return vaginal?std::optional<int>{1}:std::nullopt; }
    std::optional<int> GetAnalSegment() const { return anal?std::optional<int>{1}:std::nullopt; }
    std::optional<int> GetCrotchSegment() const { return crotch?std::optional<int>{1}:std::nullopt; }
};
struct Contact { RE::Ptr<RE::Actor> partner; int action; float velocity=0; };
struct ActorState {
    RE::Ptr<RE::Actor> actor;
    RE::Ptr<RE::Node> root;
    Geometry geometry;
    struct { bool female=false; bool any(Registry::Sex) const { return female; } } sex;
    std::vector<Contact> interactions;
};
struct Size { float length=0,radius=0; };
struct Scene {
    std::vector<ActorState> positions;
    bool VisitPositions(const std::function<bool(const ActorState&)>& visit) const {
        for(const auto& p:positions) if(visit(p)) return true;
        return false;
    }
    std::optional<Size> GetShaftSize(uint32_t) const { return std::nullopt; }
};
}
namespace Settings { bool bFallbackToTagsForDetection=true; }
struct Tags {
    std::vector<std::string> values;
    bool HasTag(std::string_view value) const { return std::ranges::find(values,value)!=values.end(); }
};
struct ActiveScene { Tags tags{{"PosTagged"}}; };
struct Stage { struct Position { std::vector<std::string> tags; }; std::vector<Position> positions; };
namespace Thread {
class Instance {
public:
    std::shared_ptr<Interaction::NiSurface::Scene> ni=std::make_shared<Interaction::NiSurface::Scene>();
    std::vector<RE::Actor*> actors;
    ActiveScene active;
    Stage stage;
    auto GetInstanceNiSurface() { return ni; }
    bool HasInstanceNiSurface() { return bool(ni); }
    void UnregisterInstanceNiSurface() { ni.reset(); }
    auto GetActiveScene() { return &active; }
    auto GetActiveStage() { return &stage; }
    const auto& GetActors() const { return actors; }
};
}
'''+header+'\n'+source+r'''
int main() {
    using namespace Thread::Interaction;
    RE::Node rootA,rootB,rootC,node;
    RE::Actor human{1,&rootA},creature{2,&rootB},third{3,&rootC};
    Thread::Instance instance;
    instance.actors={&human,&creature,&third};
    instance.stage.positions={{{"pVaginal","aOral"}},{{"aVaginal","pOral"}},{{"aVaginal"}}};
    instance.ni->positions.resize(3);
    for(int i=0;i<3;++i) {
        instance.ni->positions[i].actor={instance.actors[i]};
        instance.ni->positions[i].root={instance.actors[i]->root};
    }
    auto& humanPos=instance.ni->positions[0];
    auto& creaturePos=instance.ni->positions[1];
    auto& thirdPos=instance.ni->positions[2];
    humanPos.geometry.vaginal=true;
    humanPos.geometry.head=&node;
    thirdPos.geometry.shafts={1};
    // The creature is registered but has no shaft nodes: only this pair needs fallback.
    assert(GetInteractionFlagsImpl(&instance,&creature,&human)[aVaginal]);
    assert(GetInteractionFlagsImpl(&instance,&human,&creature)[pVaginal]);
    assert(!GetInteractionFlagsImpl(&instance,&human,&third)[pVaginal]);
    assert(HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    assert(HasActiveInteractionAllImpl(&instance,&creature,{aVaginal,pOral}));
    assert(HasActiveInteractionAnyImpl(&instance,&creature,{aVaginal}));
    assert(GetActiveInterTypesImpl(&instance,&creature,&human).size()==2);
    assert(GetPartnerByInteractionTypeImpl(&instance,&creature,aVaginal)==&human);
    auto partners=GetPartnersByInteractionTypeImpl(&instance,&human,pVaginal);
    assert(partners.size()==1 && partners[0]==&creature);
    assert(GetInteractionStringImpl(&instance,&creature).find("aVaginal")!=std::string::npos);
    assert(GetInteractionVelocityImpl(&instance,&creature,&human,aVaginal)==0);
    // Settings, scene marker and complementary partner tags remain mandatory.
    Settings::bFallbackToTagsForDetection=false;
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    Settings::bFallbackToTagsForDetection=true;
    instance.active.tags.values.clear();
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    instance.active.tags.values={"PosTagged"};
    instance.stage.positions[0].tags.clear();
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    instance.stage.positions[0].tags={"pVaginal","aOral"};
    // Supporting one role does not imply every role is detectable.
    creaturePos.geometry.shafts={1};
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,pOral));
    creaturePos.geometry.shafts.clear();
    // Unload and replacement are transient: do not fabricate tagged contacts.
    creature.root=nullptr;
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    creature.root=&node;
    assert(!HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
    creature.root=&rootB;
    // Native contacts survive merging and take precedence over the lack of tags.
    humanPos.interactions.push_back({{&third},static_cast<int>(CType::Vaginal),3.5f});
    assert(GetInteractionFlagsImpl(&instance,&human,&third)[pVaginal]);
    partners=GetPartnersByInteractionTypeImpl(&instance,&human,pVaginal);
    assert(partners.size()==2);
    assert(GetInteractionVelocityImpl(&instance,&human,&third,pVaginal)==3.5f);
    // Existing no-NiSurface fallback continues to work.
    instance.ni.reset();
    assert(HasActiveInteractionImpl(&instance,&creature,&human,aVaginal));
}
'''
run_cpp(code)
print('PASS: capability fallback through public queries, supported-no-contact, partner roles, tags, unload and native merging')
