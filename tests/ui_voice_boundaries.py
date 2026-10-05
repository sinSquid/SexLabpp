"""Actual offset conversion and voice export/sequence blocks; no engine or YAML ABI claim."""
from source_regressions import ROOT, function, run
ui=(ROOT/'src/Thread/Interface/Elements/OffsetAdjustPanel.cpp').read_text()
voice=(ROOT/'src/Registry/Define/Voice.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
namespace fs=std::filesystem;
namespace std {string format(const char*,string_view id){return string(id)+".yaml";}}
'''+function(ui,'int OffsetInputValue(')
# Extract the pre-I/O path block exactly, then return its path for inspection.
save=function(voice,'void Voice::SaveToFile(')
prefix=save[save.index('{')+1:save.index('        if (fs::exists(path))')]
code+='\nstruct Voice {std::string name;const std::string& GetId()const{return name;}fs::path path(std::string_view a_fileLocation)const{'+prefix+'return path;}};\n'
# The virtual sequence is large without allocating millions of YAML nodes or sounds.
start=voice.index('            const auto max = ',voice.index('VoiceSet::VoiceSet(const YAML::Node&'))
end=voice.index('\n        }\n        if (data.empty())',start)
block=voice[start:end]
code+=r'''
namespace RE {struct TESSound{};}
namespace Util {template<class T>T FormFromString(const std::string&){return nullptr;}}
struct Item {template<class T>T as()const{return T{};}};
struct Sequence {size_t count=16777218,accesses=0;size_t size()const{return count;}
 Item operator[](size_t i){if(i!=accesses++)throw std::runtime_error("loop stalled or skipped an index");return {};}};
void scan(Sequence& v){std::vector<std::pair<RE::TESSound*,uint8_t>>data;
'''+block+r'''
}
int main(){
 assert(OffsetInputValue(1.5f)==2);assert(OffsetInputValue(-1.5f)==-2);
 assert(OffsetInputValue(std::numeric_limits<float>::max())==std::numeric_limits<int>::max());
 assert(OffsetInputValue(-std::numeric_limits<float>::max())==std::numeric_limits<int>::min());
 assert(OffsetInputValue(static_cast<float>(std::numeric_limits<int>::max()))==std::numeric_limits<int>::max());
 assert(OffsetInputValue(std::numeric_limits<float>::quiet_NaN())==0);
 for(std::string id:{"", ".", "..", "../outside", "..\\outside", "C:outside", "folder/name"}){
  bool rejected=false;try{Voice{id}.path("voices");}catch(const std::invalid_argument&){rejected=true;}assert(rejected);
 }
 assert(Voice{"Normal Voice"}.path("voices")==fs::path("voices")/"Normal Voice.yaml");
 assert(Voice{"名字"}.path("voices")==fs::path("voices")/"名字.yaml");
 Sequence sequence;scan(sequence);assert(sequence.accesses==sequence.count);
}
'''
run('ui_voice_boundaries',code)
print('PASS: actual UI conversion, voice path prefix and large sequence loop blocks')
