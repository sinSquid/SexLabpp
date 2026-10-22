"""Emit a Windows regression using the real yaml-cpp and production StripData bodies.

Compile the emitted source with MSVC, YAML_CPP_STATIC_DEFINE and cached yaml-cpp.lib.
"""
import re
import sys
from pathlib import Path
from statistics_roundtrip import ROOT

code = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <vector>
#include <yaml-cpp/yaml.h>
#include "Util/AtomicWrite.h"
using namespace std::literals;
std::string STRIP_PATH;
namespace logger {template<class...T>void info(T&&...){} template<class...T>void error(T&&...) {}}
template<class T>struct Singleton {static T* GetSingleton(){static T x;return &x;}};
namespace RE {
 using FormID=uint32_t;
 struct BGSKeywordForm {bool ContainsKeywordString(const char*){return false;}};
 struct TESForm {FormID formID;template<class T>T* As(){return nullptr;}};
 struct File {std::string fileName="loaded.esp";};
 struct TESDataHandler : Singleton<TESDataHandler> {
  File file;
  File* LookupModByName(const std::string& n){return n==file.fileName?&file:nullptr;}
  FormID LookupFormID(uint32_t id,const std::string& n){return n==file.fileName?(0x01000000|id):0;}
  File* LookupLoadedModByIndex(uint8_t i){return i==1?&file:nullptr;}
  File* LookupLoadedLightModByIndex(uint16_t){return nullptr;}
 };
}
'''
for path in ['src/UserData/StripData.h','src/UserData/StripData.cpp']:
    code += re.sub(r'^#(?:include|pragma).*$', '', (ROOT/path).read_text(), flags=re.M)
code += r'''
int main(int argc,char** argv){
 assert(argc==2);std::filesystem::path dir=argv[1];std::filesystem::create_directories(dir);
 STRIP_PATH=(dir/"strip.yaml").string();
 Util::AtomicWrite(STRIP_PATH,"loaded.esp:\n  1: -1\n  2: 1\nunavailable.esp:\n  3: -1\n");
 auto* data=UserData::StripData::GetSingleton();data->Load();
 RE::TESForm a{0x01000001},b{0x01000002};
 assert(data->CheckStrip(&a)==UserData::Strip::NoStrip);
 data->RemoveArmor(&a);data->Save();
 auto saved=YAML::LoadFile(STRIP_PATH);
 assert(!saved["loaded.esp"][1]&&saved["loaded.esp"][2].as<int>()==1);
 assert(saved["unavailable.esp"][3].as<int>()==-1);
 data->Load();assert(data->CheckStrip(&a)==UserData::Strip::None);
 data->RemoveArmorAll();data->Save();saved=YAML::LoadFile(STRIP_PATH);
 assert(!saved["loaded.esp"]&&saved["unavailable.esp"][3].as<int>()==-1);
 // A malformed reload must retain the previous live map.
 data->AddArmor(&a,UserData::Strip::Always);
 Util::AtomicWrite(STRIP_PATH,"loaded.esp: [unterminated");data->Load();
 assert(data->CheckStrip(&a)==UserData::Strip::Always);
 assert(data->CheckStrip(nullptr)==UserData::Strip::None);
}
'''
if __name__=='__main__':
    target=Path(sys.argv[1]);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(code)
