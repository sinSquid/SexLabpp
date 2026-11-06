// Compile on Windows with the real yaml-cpp package, using engine stand-ins only.
#include <yaml-cpp/yaml.h>
#include <cassert>
#include <cstdint>
#include <fstream>
#include <map>
#include <string>
#include <vector>
using namespace std::literals;
template<class T> struct Singleton {};
namespace logger { template<class... T> void info(T&&...){} template<class... T> void error(T&&...){} }
namespace RE {
using FormID=uint32_t;
struct TESFile {const char* fileName;uint8_t compileIndex;};
struct BGSKeywordForm {bool ContainsKeywordString(const char*){return false;}};
struct TESForm {
 FormID formID;TESFile* file;uint32_t local;
 TESFile* GetFile(int){return file;}
 uint32_t GetLocalFormID(){return local;}
 template<class T>T* As(){return nullptr;}
};
struct TESDataHandler {
 TESFile regular{"Loaded.esp",1},light{"Light.esl",0xFE},disabled{"Disabled.esp",0xFF};
 static TESDataHandler* GetSingleton(){static TESDataHandler h;return &h;}
 TESFile* LookupModByName(const std::string& n){if(!_stricmp(n.c_str(),regular.fileName))return &regular;if(!_stricmp(n.c_str(),light.fileName))return &light;if(!_stricmp(n.c_str(),disabled.fileName))return &disabled;return nullptr;}
 FormID LookupFormID(uint32_t id,const std::string& n){return LookupModByName(n)==&regular?0x01000000|id:0xFE000000|id;}
 TESFile* LookupLoadedModByIndex(uint8_t n){return n==1?&regular:nullptr;}
 TESFile* LookupLoadedLightModByIndex(uint16_t n){return n==0?&light:nullptr;}
};
}
const char* testPath;
#define STRIP_PATH testPath
#include "../src/UserData/StripData.h"
#include "../src/UserData/StripData.cpp"
int main(int argc,char** argv) {
 assert(argc==2);testPath=argv[1];
 std::ofstream(testPath)<<"loaded.ESP:\n  0x123: -1\n  292: 1\nLoaded.esp:\n  0x123: -1\n  291: -1\nLight.esl:\n  0x125: 1\nMissing.esp:\n  99: -1\nDisabled.esp:\n  98: -1\n";
 auto* h=RE::TESDataHandler::GetSingleton();
 RE::TESForm first{0x01000123,&h->regular,0x123},second{0x01000124,&h->regular,0x124},light{0xFE000125,&h->light,0x125};
 UserData::StripData data;data.Load();
 assert(data.CheckStrip(&first)==UserData::Strip::NoStrip);
 data.Save(); // Existing numeric spellings and plugin-name case variants must all be removed.
 data.RemoveArmor(&first);data.Save();
 UserData::StripData reloaded;reloaded.Load();
 assert(reloaded.CheckStrip(&first)==UserData::Strip::None);
 assert(reloaded.CheckStrip(&second)==UserData::Strip::Always);
 reloaded.RemoveArmor(&light);reloaded.Save();
 UserData::StripData again;again.Load();assert(again.CheckStrip(&light)==UserData::Strip::None);
 again.RemoveArmorAll();again.Save();
 const auto saved=YAML::LoadFile(testPath);
 assert(!saved["loaded.ESP"]&&!saved["Loaded.esp"]&&!saved["Light.esl"]);
 assert(saved["Missing.esp"][99].as<int>()==-1);
 assert(saved["Disabled.esp"][98].as<int>()==-1);
}
