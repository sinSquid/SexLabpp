"""Actual Voice export and filesystem publication; YAML/engine values are stand-ins."""
from source_regressions import ROOT, function, run
production=(ROOT/'src/Registry/Define/Voice.cpp').read_text()
code=r'''
#include <cassert>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>
#include <string_view>
#include <vector>
namespace logger { template<class... T> void info(T&&...) {} template<class... T> void error(T&&...) {} }
#include "Util/SaveQueue.h"
#include "Util/StringUtil.h"
namespace fs=std::filesystem;
namespace std { string format(const char*, string_view id) {return string(id)+".yaml";} }
namespace RE { enum class SEXES {kNone,kMale,kFemale}; }
namespace magic_enum { template<class T> std::string_view enum_name(T) {return "Unknown";} }
namespace YAML {
 enum class NodeType {Sequence};
 struct Node {
  Node()=default; Node(NodeType) {}
  Node operator[](const char*) const {return {};}
  template<class T> Node& operator=(const T&) {return *this;}
  template<class T> void push_back(const T&) {}
  bool IsDefined() const {return false;}
 };
 std::function<void()> beforeDump;
 std::string Dump(const Node&) {if(beforeDump) beforeDump(); return "exported";}
}
struct Race {std::string_view AsString() const {return "Human";}};
struct Tags {std::vector<std::string> AsVector() const {return {};}};
struct Set {YAML::Node AsYaml() const {return {};}};
struct Voice {
 std::string name="voice",displayName; int pitch=0;
 RE::SEXES sex=RE::SEXES::kNone; std::vector<Race> races; Tags tags; Set defaultset; std::vector<Set> extrasets;
 std::string GetId() const {return name;}
 void SaveToFile(std::string_view) const;
};
'''
# StringUtil's unrelated helpers require the project PCH; isolate the actual stem helper.
code=code.replace('#include "Util/StringUtil.h"', 'namespace Util {'+function((ROOT/'src/Util/StringUtil.h').read_text(),'constexpr bool IsSafeFileStem(')+'}')
code+=function(production,'void Voice::SaveToFile(')
code+=r'''
std::string read(const fs::path& p) {std::ifstream f(p);return {std::istreambuf_iterator<char>(f),{}};}
int main() {
 const auto directory=fs::temp_directory_path()/("sexlab-voice-publication-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
 fs::create_directories(directory);
 const auto target=directory/"voice.yaml"; Voice voice;
 YAML::beforeDump=[&]{std::ofstream(target)<<"competing-writer";};
 voice.SaveToFile(directory.string());
 assert(read(target)=="competing-writer");
 fs::remove(target); YAML::beforeDump={}; voice.SaveToFile(directory.string());
 assert(read(target)=="exported");
 std::ofstream(target)<<"existing"; voice.SaveToFile(directory.string()); assert(read(target)=="existing");
 // Existing default callers retain replacement behavior.
 Util::AtomicWrite(target,"updated"); assert(read(target)=="updated");
 for(const auto& e:fs::directory_iterator(directory)) assert(e.path()==target);
 fs::remove_all(directory);
}
'''
run('voice_export_publication',code)
print('PASS: Voice export preserves a competing publication and existing files')
