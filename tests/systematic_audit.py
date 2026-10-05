"""Boundary regressions for the systematic audit; engine calls use stand-ins."""
from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
from source_regressions import ROOT, function, run

BASE = Path(os.environ.get('REVIEW_BASE_DIR', ROOT))


def header_linkage():
    # Include the actual header in two independent translation units, at -O0.
    stub = r'''
#include <cstddef>
#include <string>
namespace REL { struct Module { static bool IsVR() { return false; } }; }
namespace RE {
struct Main { static Main* GetSingleton() { return nullptr; } };
struct UI { static UI* GetSingleton() { return nullptr; } bool GameIsPaused() { return false; } };
struct ConsoleLog { static ConsoleLog* GetSingleton() { return nullptr; } void Print(const char*, const char*) {} };
struct TESActorBase {};
struct Actor { TESActorBase* GetTemplateActorBase() { return nullptr; } TESActorBase* GetActorBase() { return nullptr; } };
}
#include "Util/Misc.h"
'''
    with tempfile.TemporaryDirectory(prefix='sexlab-odr-') as tmp:
        root = Path(tmp)
        (root / 'a.cpp').write_text(stub + '\nint other(); int main() { return other(); }\n')
        (root / 'b.cpp').write_text(stub + '\nint other() { RE::Actor actor; return Util::GetLeveledActorBase(&actor) != nullptr; }\n')
        binary = root / 'odr'
        subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++20', '-O0', '-I', str(BASE / 'src'),
                        str(root / 'a.cpp'), str(root / 'b.cpp'), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def property_boundaries():
    source = (BASE / 'src/Util/Script.h').read_text()
    code = r'''
#include <cassert>
#include <memory>
#include <string>
#include <type_traits>
#include <utility>
namespace std { template<class T> constexpr auto to_underlying(T v) { return static_cast<std::underlying_type_t<T>>(v); } }
namespace logger { template<class... T> void error(T&&...) {} }
enum class RawType { kBool, kInt, kFloat, kOther };
struct Type { RawType raw; RawType GetRawType() const { return raw; } };
struct Variable { double value{}; Type type{RawType::kInt}; Type GetType() const { return type; } };
struct Object { Variable data; Variable* GetProperty(const std::string& name) { return name == "exists" ? &data : nullptr; } };
using ObjectPtr = std::shared_ptr<Object>;
namespace RE {
using BSFixedString = std::string;
namespace BSScript {
template<class T> T UnpackValue(Variable* p) { assert(p); return static_cast<T>(p->value); }
template<class T> void PackValue(Variable* p, T value) { assert(p); p->value = value; }
}
}
'''
    for signature, prefix in [
        ('inline T GetProperty', 'template<class T>\n'),
        ('inline T GetTrivialProperty', 'template<class T>\n'),
        ('inline void SetProperty', 'template<class T>\n'),
    ]:
        code += prefix + function(source, signature) + '\n'
    code += r'''
int main() {
    auto object = std::make_shared<Object>();
    SetProperty(object, "exists", 42);
    assert(GetProperty<int>(object, "exists") == 42);
    assert(GetTrivialProperty<int>(object, "exists") == 42);
    object->data.type.raw = RawType::kBool;
    assert(GetTrivialProperty<bool>(object, "exists"));
    object->data.type.raw = RawType::kFloat;
    object->data.value = 2.5;
    assert(GetTrivialProperty<float>(object, "exists") == 2.5f);
    assert(GetTrivialProperty<int>(object, "missing") == 0);
    assert(GetProperty<int>(object, "missing") == 0);
    assert(GetTrivialProperty<float>(nullptr, "exists") == 0.0f);
    assert(GetProperty<int>(nullptr, "exists") == 0);
    SetProperty(object, "missing", 7);
    SetProperty(ObjectPtr{}, "exists", 7);
    assert(object->data.value == 2.5);
    object->data.type.raw = RawType::kOther;
    assert(GetTrivialProperty<int>(object, "exists") == 0);
}
'''
    run('script_property_boundaries', code)


def fragment_sex_bits():
    source = (BASE / 'src/Registry/Define/Fragment.cpp').read_text()
    header = (BASE / 'src/Registry/Define/Fragment.h').read_text()
    sex_header = (BASE / 'src/Registry/Define/Sex.h').read_text()
    value_enum = re.search(r'enum Value\s*\{.*?\};', header, re.S).group()
    sex_enum = re.search(r'enum class Sex : uint8_t\s*\{.*?\};', sex_header, re.S).group()
    code = r'''
#include <cassert>
#include <cstdint>
namespace REX { template<class E> struct EnumSet {
    unsigned value{};
    EnumSet() = default;
    EnumSet(E v): value(static_cast<unsigned>(v)) {}
    void set(E v) { value |= static_cast<unsigned>(v); }
    bool any(E v) const { return (value & static_cast<unsigned>(v)) != 0; }
    template<class... T> bool all(T... v) const { return ((value & (static_cast<unsigned>(v) | ...)) == (static_cast<unsigned>(v) | ...)); }
}; }
namespace Registry {
'''
    code += sex_enum + '\nstruct ActorFragment {\n' + value_enum + r'''
    REX::EnumSet<Value> value;
    REX::EnumSet<Sex> GetSex() const;
    bool IsHuman() const { return value.any(Human); }
};
'''
    code += function(source, 'REX::EnumSet<Sex> ActorFragment::GetSex') + '\n}\n'
    code += r'''
int main() {
    using namespace Registry;
    // Creature race occupies bits 3..8; it must never add a human Futa flag.
    for (unsigned race = 1; race < 64; ++race) {
        for (auto sex : {ActorFragment::Male, ActorFragment::Female}) {
            ActorFragment fragment;
            fragment.value.value = (race << 3) | sex;
            assert(fragment.GetSex().value == static_cast<unsigned>(sex));
        }
    }
    ActorFragment human;
    human.value.value = ActorFragment::Human | ActorFragment::Futa | ActorFragment::Vampire;
    assert(human.GetSex().all(Sex::Futa));
    assert(!human.GetSex().any(Sex::Male));
}
'''
    code = '#include <initializer_list>\n' + code
    run('fragment_sex_bits', code)


def native_actor_boundaries():
    source = (BASE / 'src/Papyrus/sslThreadModel.cpp').read_text()
    code = r'''
#include <cassert>
namespace RE { struct Actor {}; struct TESQuest {}; }
struct VM { int errors{}; void TraceStack(const char*, int) { ++errors; } };
struct Instance {
    int changes{};
    bool SetNextPermutation(RE::Actor* actor) { assert(actor); ++changes; return true; }
    void UpdatePlacement(RE::Actor* actor) { assert(actor); ++changes; }
} storage;
bool available = true;
#define QUESTARGS VM* a_vm, int a_stackID, RE::TESQuest* a_qst
#define GET_INSTANCE(ret) auto* instance = available ? &storage : nullptr; if (!instance) { return ret; }
'''
    code += function(source, 'bool SetNextPermutation(QUESTARGS') + '\n'
    code += function(source, 'void UpdatePlacement(QUESTARGS') + '\n'
    code += r'''
int main() {
    VM vm; RE::TESQuest quest; RE::Actor actor;
    assert(!SetNextPermutation(&vm, 0, &quest, nullptr));
    UpdatePlacement(&vm, 0, &quest, nullptr);
    assert(storage.changes == 0 && vm.errors == 2);
    assert(SetNextPermutation(&vm, 0, &quest, &actor));
    UpdatePlacement(&vm, 0, &quest, &actor);
    assert(storage.changes == 2);
    available = false;
    assert(!SetNextPermutation(&vm, 0, &quest, &actor));
    UpdatePlacement(&vm, 0, &quest, &actor);
    assert(storage.changes == 2);
}
'''
    run('native_actor_boundaries', code)


def stage_weight_selection():
    source = (BASE / 'src/Papyrus/sslThreadModel.cpp').read_text()
    code = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
namespace RE { struct TESQuest {}; using BSFixedString = std::string; }
namespace Registry { struct TagData { uint32_t count{}; TagData() = default; TagData(const std::vector<std::string>&) {} uint32_t CountTags(const TagData&) const { return count; } }; }
struct Stage { Registry::TagData tags; };
struct Scene { std::vector<const Stage*> adjacent; const auto* GetAdjacentStages(const Stage*) { return &adjacent; } };
struct Instance { Scene* scene{}; Stage* stage{}; Scene* GetActiveScene() { return scene; } Stage* GetActiveStage() { return stage; } } storage;
struct VM { void TraceStack(const char*, int) {} };
namespace Random {
uint64_t chosen{}, lastMaximum{};
template<class T> T draw(T lower, T upper) { assert(lower == 0 && chosen <= upper); lastMaximum = upper; return static_cast<T>(chosen); }
int draw(const std::vector<int>& values) { lastMaximum = values.size()-1; return values.at(chosen); }
}
#define QUESTARGS VM* a_vm, int a_stackID, RE::TESQuest* a_qst
#define GET_INSTANCE(ret) auto* instance = &storage
'''
    code += function(source, 'int SelectNextStage(QUESTARGS') + '\n'
    code += r'''
int main() {
    VM vm; RE::TESQuest quest; Scene scene; Stage stages[3];
    assert(SelectNextStage(&vm, 0, &quest, {}) == 0);
    storage.scene = &scene; storage.stage = &stages[0];
    assert(SelectNextStage(&vm, 0, &quest, {}) == 0);
    scene.adjacent = {&stages[0], &stages[1], &stages[2]};
    for (uint32_t a=0; a<8; ++a) for (uint32_t b=0; b<8; ++b) for (uint32_t c=0; c<8; ++c) {
        stages[0].tags.count=a; stages[1].tags.count=b; stages[2].tags.count=c;
        std::vector<int> reference;
        for (int i=0; i<3; ++i) reference.resize(reference.size()+stages[i].tags.count+1, i);
        for (size_t choice=0; choice<reference.size(); ++choice) {
            Random::chosen=choice;
            assert(SelectNextStage(&vm, 0, &quest, {}) == reference[choice]);
            assert(Random::lastMaximum == reference.size()-1);
        }
    }
    // A very large score must not cause score-proportional allocation or wrap.
    stages[0].tags.count = UINT32_MAX; stages[1].tags.count = 0; stages[2].tags.count = 0;
    Random::chosen = uint64_t{UINT32_MAX}+1;
    assert(SelectNextStage(&vm, 0, &quest, {}) == 1);
}
'''
    run('stage_weight_selection', code)


def legacy_geometry():
    source = (BASE / 'src/Thread/NiNode/Legacy/LegacyNiMath.cpp').read_text()
    code = r'''
#include <algorithm>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <random>
struct Vec {
 float x,y,z;
 Vec operator+(Vec b) const { return {x+b.x,y+b.y,z+b.z}; }
 Vec operator-(Vec b) const { return {x-b.x,y-b.y,z-b.z}; }
 Vec operator*(float t) const { return {x*t,y*t,z*t}; }
 float Dot(Vec b) const { return x*b.x+y*b.y+z*b.z; }
 float SqrLength() const { return Dot(*this); }
};
struct Segment {
 Vec first,second; bool isPoint;
 Segment(Vec a, Vec b): first(a), second(b), isPoint((b-a).SqrLength()==0) {}
 Vec Vector() const { return second-first; }
};
''' + function(source, 'Segment ClosestSegmentBetweenSegments') + r'''
int main() {
 Segment a{{0,0,0},{2,0,0}}, b{{1,-2,0},{1,2,0}};
 assert(ClosestSegmentBetweenSegments(a,b).Vector().SqrLength()<1e-6f);
 std::mt19937 rng(91); std::uniform_real_distribution<float> random(-5,5);
 auto point=[&]{ return Vec{random(rng),random(rng),random(rng)}; };
 for(int n=0;n<1000;++n) {
  auto p=point(),q=point(),r=point(),s=point();
  if(n%10==0)s=r+(q-p);
  if(n%17==0)q=p;
  if(n%19==0)s=r;
  Segment x{p,q}, y{r,s};
  auto nearest=ClosestSegmentBetweenSegments(x,y);
  auto d=nearest.Vector().SqrLength();
  assert(std::abs(d-ClosestSegmentBetweenSegments(y,x).Vector().SqrLength())<0.001f);
  for(int i=0;i<=100;++i) {
   float t=i/100.f;
   assert(d<=(x.first+x.Vector()*t-nearest.second).SqrLength()+0.001f);
   assert(d<=(y.first+y.Vector()*t-nearest.first).SqrLength()+0.001f);
  }
 }
}
'''
    run('legacy_closest_segments', code)


def navigation_placeholders():
    source = (BASE / 'src/Thread/Interface/StageSelectMenu.cpp').read_text()
    code = r'''
#include <algorithm>
#include <cassert>
#include <charconv>
#include <cctype>
#include <string>
#include <string_view>
#include <vector>
namespace RE { struct Actor { const char* GetName() const { return "Alice"; } }; }
''' + function(source, 'std::string ResolveNavTextPlaceholders') + r'''
int main() {
 RE::Actor actor;
 std::vector<RE::Actor*> actors{&actor,nullptr};
 assert(ResolveNavTextPlaceholders("Hi {0}: {1}/{2}",actors)=="Hi Alice: {}/{}");
 assert(ResolveNavTextPlaceholders("{0000} {x} {} {-1} {",actors)=="Alice {x} {} {-1} {");
 assert(ResolveNavTextPlaceholders("{999999999999999999999999999999}",actors)=="{}");
}
'''
    run('navigation_placeholders', code)


def overlay_layout():
    source = (BASE / 'src/Thread/Interface/Elements/EnjBarsOverlay.cpp').read_text()
    code = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstddef>
namespace ImGuiMCP { struct IO { struct {float x,y;} DisplaySize; } io; auto* GetIO(){return &io;} }
namespace UI {
struct Scale { float factor; float Px(float x){return factor*x;} float TextPx(float x){return Px(x);}
 float Clamp(float low,float percent,float high,float axis){return std::clamp(axis*percent*.01f,Px(low),Px(high));} };
namespace Theme { struct {float body=10.5f,metadata=8.5f,smallText=8,detail=7.5f;} FontSize; }
}
struct EnjBarsOverlay {
 struct Layout {float zoneW,barGap,innerGp,frameH,lblPad,nameFt,valFt,intrFt,fbFt,edgeH,edgeV,lblRowH,unitH,winH;};
 static Layout GetLayout(UI::Scale&,size_t);
};
// Check the standard clamp precondition even on release-mode standard libraries.
template<class T> T checked_clamp(T value,T low,T high){assert(low<=high);return std::clamp(value,low,high);}
'''
    code += function(source, 'EnjBarsOverlay::Layout EnjBarsOverlay::GetLayout').replace('std::clamp', 'checked_clamp')
    code += r'''
int main(){
 for(float width:{1280.f,1920.f,3440.f,5120.f}) for(float height:{720.f,1080.f,1440.f})
 for(float multiplier:{.5f,1.f,2.5f}) {
  ImGuiMCP::io.DisplaySize={width,height};
  float shortest=std::min(width,height);
  float resolution=shortest<=900 ? (4.f/3)*(shortest/900) : (4.f/3)+(shortest-900)/1260*(3-4.f/3);
  UI::Scale scale{resolution*multiplier};
  auto layout=EnjBarsOverlay::GetLayout(scale,3);
  assert(std::isfinite(layout.zoneW) && layout.zoneW>0 && layout.zoneW<=scale.Px(360));
 }
}
'''
    run('overlay_layout', code)


def hash_cli():
    script = BASE / 'scripts/hashing.py'
    value = (5 << 44) | (6 << 33)  # Two humans, male then female, followed by empty slots.
    expected = subprocess.check_output([sys.executable, str(script), '-b', format(value, '055b')], text=True)
    for flag, argument in [('-d', str(value)), ('-b', format(value, 'b'))]:
        actual = subprocess.check_output([sys.executable, str(script), flag, argument], text=True)
        assert actual == expected
        assert actual.count('Value:') == 2
        assert 'Male (1)' in actual and 'Female (2)' in actual
    for flag, argument in [('-d', '-1'), ('-d', str(1 << 55)), ('-b', '102'), ('-b', '1' * 56)]:
        result = subprocess.run([sys.executable, str(script), flag, argument], capture_output=True, text=True)
        assert result.returncode != 0 and 'Traceback' not in result.stderr


if __name__ == '__main__':
    header_linkage()
    property_boundaries()
    fragment_sex_bits()
    native_actor_boundaries()
    stage_weight_selection()
    legacy_geometry()
    navigation_placeholders()
    overlay_layout()
    hash_cli()
    print('PASS: linkage, property/native boundaries, fragment bits, weighted selection, geometry, navigation, layout and hash CLI (engine stand-ins)')
