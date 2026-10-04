"""Production methods with engine stand-ins for the full file review fixes."""
from source_regressions import ROOT, function, run

math=(ROOT/'src/Thread/NiNode/NiMath.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <iostream>
#include <random>
struct Vec {
 float x,y,z;
 Vec operator+(Vec b)const{return {x+b.x,y+b.y,z+b.z};}
 Vec operator-(Vec b)const{return {x-b.x,y-b.y,z-b.z};}
 Vec operator*(float t)const{return {x*t,y*t,z*t};}
 float Dot(Vec b)const{return x*b.x+y*b.y+z*b.z;}
 float SqrLength()const{return Dot(*this);}
};
struct Segment {
 Vec first,second;
 bool IsPoint()const{return (second-first).SqrLength()==0;}
 Vec Vector()const{return second-first;}
 Segment ShortestSegmentTo(const Segment&)const;
};
'''+function(math,'Segment Segment::ShortestSegmentTo')+r'''
int main(){
 Segment a{{0,0,0},{2,0,0}},b{{1,-2,0},{1,2,0}};
 assert(a.ShortestSegmentTo(b).Vector().SqrLength()<1e-6f);
 Segment p{{-1,0,0},{-1,0,0}},q{{0,0,0},{0,0,0}};
 assert(std::abs(p.ShortestSegmentTo(q).Vector().SqrLength()-1)<1e-6f);
 std::mt19937 rng(91);std::uniform_real_distribution<float> rand(-5,5);
 auto point=[&]{return Vec{rand(rng),rand(rng),rand(rng)};};
 for(int n=0;n<1000;++n){
  Segment x{point(),point()},y{point(),point()};
  if(n%10==0)y.second=y.first+x.Vector();
  if(n%17==0)x.second=x.first;
  const auto nearest=x.ShortestSegmentTo(y);
  float d=nearest.Vector().SqrLength(),reverse=y.ShortestSegmentTo(x).Vector().SqrLength();
  assert(std::abs(d-reverse)<0.001f);
  // Independent geometric condition: neither endpoint can be improved by any
  // sampled point on its segment while the opposite closest endpoint is fixed.
  for(int i=0;i<=100;++i){float t=i/100.f;
   assert(d<=(x.first+x.Vector()*t-nearest.second).SqrLength()+0.001f);
   assert(d<=(y.first+y.Vector()*t-nearest.first).SqrLength()+0.001f);
  }
 }
 std::cout<<"PASS: production closest-segment crossing, point/parallel cases and 1000 randomized symmetry/optimality checks\n";
}
'''
run('geometry',code)

header=(ROOT/'src/Papyrus/sslLibrary/Serialize.h').read_text().replace('#pragma once','')
code=r'''
#include <map>
#include <vector>
#include <string>
#include <mutex>
#include <thread>
#include <algorithm>
#include <cassert>
#include <cstring>
#include <cstdint>
#include <iostream>
namespace RE {using FormID=uint32_t;using BSFixedString=std::string;}
template<class T>struct Singleton {};
namespace logger{template<class... T>void info(T&&...){} template<class... T>void error(T&&...){} }
namespace SKSE {struct SerializationInterface {
 std::vector<char> bytes;size_t position=0;
 bool WriteRecordData(const void* data,uint32_t n){auto* p=static_cast<const char*>(data);bytes.insert(bytes.end(),p,p+n);return true;}
 uint32_t ReadRecordData(void* data,uint32_t n){auto count=std::min<size_t>(n,bytes.size()-position);std::memcpy(data,bytes.data()+position,count);position+=count;return static_cast<uint32_t>(count);}
 bool ResolveFormID(uint32_t old,uint32_t& resolved){resolved=old;return old!=99;}
};}
'''+header+r'''
int main(){
 Papyrus::Tracking data;
 data.Add(data._factions,99,"missing");data.Add(data._factions,2,"valid");data.Add(data._actors,3,"event");
 data.Add(data._actors,3,"event");assert(data.Callbacks(data._actors,3).size()==1);
 SKSE::SerializationInterface io;data.Save(&io);data.Revert(nullptr);data.Load(&io,static_cast<uint32_t>(io.bytes.size()));
 assert(!data.Contains(data._factions,99)&&data.Contains(data._factions,2));
 const auto snapshot=data.Callbacks(data._actors,3);data.Remove(data._actors,3,"event");assert(!data.Contains(data._actors,3)&&snapshot[0]=="event");
 // Every truncation must reject the entire record, without partial registration.
 for(size_t n=0;n<io.bytes.size();++n){auto bad=io;bad.bytes.resize(n);bad.position=0;data.Load(&bad,static_cast<uint32_t>(n));assert(data._actors.empty()&&data._factions.empty());}
 auto invalid=io;invalid.position=0;std::fill(invalid.bytes.begin(),invalid.bytes.begin()+8,'\xff');data.Load(&invalid,static_cast<uint32_t>(invalid.bytes.size()));assert(data._actors.empty());
 auto delimiter=io;delimiter.position=0;delimiter.bytes.back()=0;data.Load(&delimiter,static_cast<uint32_t>(delimiter.bytes.size()));assert(data._actors.empty()&&data._factions.empty());
 std::vector<std::thread> workers;
 for(int i=0;i<4;++i)workers.emplace_back([&]{for(int j=0;j<1000;++j){data.Add(data._actors,3,"event");auto callbacks=data.Callbacks(data._actors,3);data.Remove(data._actors,3,"event");}});
 for(auto& t:workers)t.join();
 std::cout<<"PASS: production tracking v1 roundtrip, unresolved IDs, every truncation, malformed counts/delimiter and concurrent callbacks\n";
}
'''
run('tracking',code)

source=(ROOT/'src/Papyrus/SexLabUtil.cpp').read_text()
a=source.index('    namespace\n');b=source.index('    std::vector<RE::Actor*> MakeActorArray',a)
code=r'''
#include <vector>
#include <type_traits>
#include <cmath>
#include <limits>
#include <cassert>
#include <iostream>
namespace RE {struct StaticFunctionTag {};}
'''+source[a:b]+r'''
int main(){assert(IntMinMaxValue(nullptr,{4,-1,9},true)==9);assert(IntMinMaxIndex(nullptr,{4,-1,9},false)==1);assert(IntMinMaxValue(nullptr,{},true)==0);
 float nan=std::numeric_limits<float>::quiet_NaN();assert(FloatMinMaxIndex(nullptr,{nan,3,-2,nan},false)==2);assert(FloatMinMaxValue(nullptr,{nan,3,-2},true)==3);assert(std::isnan(FloatMinMaxValue(nullptr,{nan},true)));
 std::cout<<"PASS: production min/max shared scan preserves empty and NaN behavior\n";}
'''
run('minmax',code)

header=(ROOT/'src/Registry/Define/Transform.h').read_text()
code=r'''
#include <vector>
#include <cstdint>
#include <cmath>
#include <cassert>
#include <iostream>
namespace RE {struct TESObjectREFR;struct NiPoint3 {float x,y,z;};}
namespace Decode {class Reader;}
namespace glm {
struct vec3 {float x,y,z;vec3(float n):x(n),y(n),z(n){}bool operator==(const vec3&)const=default;};
struct vec4 {float x,y,z,w;};
float distance(vec3 a,vec3 b){return std::sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z));}
}
'''+function(header,'struct Coordinate')+r''';
int main(){Coordinate value;assert(value.rotation==0 && value.location.x==0 && value.location.y==0 && value.location.z==0);std::cout<<"PASS: production default coordinate is the identity transform\n";}
'''
run('coordinate',code)

source=(ROOT/'src/Registry/Define/Voice.cpp').read_text()
code=r'''
#include <vector>
#include <cstdint>
#include <limits>
#include <algorithm>
#include <cassert>
#include <iostream>
namespace RE {struct TESSound {int id;};}
enum class LegacyVoice {Hot,Mild,Medium};
enum class VoiceAnnotation {None=0,Submissive=1,Dominant=2,Muffled=128};
namespace REX {template<class E>struct EnumSet {E value;EnumSet(E x):value(x){}bool operator!=(E x)const{return value!=x;}uint32_t underlying()const{return static_cast<uint32_t>(value);}};}
struct VoiceSet {
 static inline int copies=0;
 std::vector<std::pair<RE::TESSound*,uint8_t>> data;
 RE::TESSound* orgasm=nullptr;
 VoiceAnnotation flags=VoiceAnnotation::None;
 VoiceSet(RE::TESSound* s,VoiceAnnotation a):data{{s,0}},flags(a){}
 VoiceSet(const VoiceSet& o):data(o.data),orgasm(o.orgasm),flags(o.flags){++copies;}
 bool IsValid(REX::EnumSet<VoiceAnnotation> a)const{return a.value==flags;}
 RE::TESSound* GetOrgasm()const{return orgasm;}
 RE::TESSound* Get(LegacyVoice)const;
 RE::TESSound* Get(uint32_t)const;
};
struct Voice {
 VoiceSet defaultset;
 std::vector<VoiceSet> extrasets;
 const VoiceSet& GetApplicableSet(REX::EnumSet<VoiceAnnotation>)const;
 RE::TESSound* PickSound(LegacyVoice)const;
 RE::TESSound* PickOrgasmSound(REX::EnumSet<VoiceAnnotation>)const;
};
'''
for sig in ('const VoiceSet& Voice::GetApplicableSet','RE::TESSound* Voice::PickSound(LegacyVoice','RE::TESSound* Voice::PickOrgasmSound','RE::TESSound* VoiceSet::Get(uint32_t','RE::TESSound* VoiceSet::Get(LegacyVoice'):
 code+=function(source,sig)+'\n'
code+=r'''
int main(){RE::TESSound base{1},sub{2};Voice v{{&base,VoiceAnnotation::None},{{&base,VoiceAnnotation::None},{&sub,VoiceAnnotation::Submissive}}};
 assert(v.PickSound(LegacyVoice::Medium)==&sub);assert(v.PickSound(LegacyVoice::Mild)==&base);
 VoiceSet::copies=0;assert(v.PickOrgasmSound(VoiceAnnotation::Submissive)==&sub);assert(VoiceSet::copies==0);
 v.extrasets.clear();assert(v.PickSound(LegacyVoice::Medium)==&base);
 std::cout<<"PASS: production legacy conditional voice selection and zero-copy orgasm lookup\n";}
'''
run('voices',code)

# Source contracts only: these paths still require Papyrus/ImGui runtime checks.
source=(ROOT/'dist/Source/Scripts/SexLabFramework.psc').read_text()
assert 'Failed to add some actors to thread")\n    thread.EndAnimation(true)\n    return none' in source
source=(ROOT/'src/Thread/Interface/StageSelectMenu.cpp').read_text()
block=source[source.index('        // Edges\n'):source.index('        // Nodes\n',source.index('        // Edges\n'))]
assert 'if (!inst) {\n            ImGuiMCP::ImDrawListManager::PopClipRect(dl);\n            return;' in block
print('PASS: source contracts for failed-start cleanup and graph clip restoration (not game execution)')

source=(ROOT/'src/Registry/Util/RayCast/bhkLinearCastCollector.h').read_text()
code='#include <cstdint>\n#include <cassert>\n#include <iostream>\n'+function(source,'constexpr bool IsRaycastLayerAccepted')+r'''
int main(){for(uint32_t i=0;i<128;++i){bool expected=i<32 && ((0x40122716u >> (i%32)) & 1u);assert(IsRaycastLayerAccepted(i)==expected);assert(IsRaycastLayerAccepted(i|0x8000)==expected);}std::cout<<"PASS: raycast layer mask handles every 7-bit value without oversized shifts\n";}
'''
run('raycast_mask',code)
