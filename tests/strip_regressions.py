"""Production strip load/save/remove behavior with in-memory YAML and engine stand-ins."""
from source_regressions import ROOT, run
header=(ROOT/'src/UserData/StripData.h').read_text().replace('#pragma once','')
source=(ROOT/'src/UserData/StripData.cpp').read_text()
source='\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
code=r'''
#include <map>
#include <memory>
#include <string>
#include <set>
#include <mutex>
#include <cassert>
#include <iostream>
#include <stdexcept>
using namespace std::string_literals;
namespace logger { template<class... T> void error(T&&...) {} template<class... T> void info(T&&...) {} }
template<class T> struct Singleton {};
constexpr const char* STRIP_PATH="strip";
namespace YAML {
struct Key { std::string value; bool operator<(const Key& o)const{return value<o.value;} template<class T>T as()const {if constexpr(std::is_same_v<T,std::string>)return value;else return static_cast<T>(std::stoul(value));} };
enum class NodeType { Map };
struct Node {
    std::shared_ptr<std::map<Key,Node>> children=std::make_shared<std::map<Key,Node>>();
    std::string scalar;
    Node()=default; Node(NodeType){}
    Node& operator[](const std::string& k){return (*children)[Key{k}];}
    Node& operator[](uint32_t k){return (*this)[std::to_string(k)];}
    Node& operator=(int32_t n){scalar=std::to_string(n);return *this;}
    template<class T>T as()const {if constexpr(std::is_same_v<T,std::string>) return scalar;else return static_cast<T>(std::stoi(scalar));}
    auto begin()const{return children->cbegin();} auto end()const{return children->cend();}
    size_t size()const{return children->size();}
};
Node input;
Node LoadFile(const char*){return input;}
Node Clone(const Node& n){Node copy;copy.scalar=n.scalar;for(const auto& [k,v]:*n.children)(*copy.children)[k]=Clone(v);return copy;}
std::string Dump(const Node& n){std::string s=n.scalar;for(const auto& [k,v]:*n.children)s+="["+k.value+":"+Dump(v)+"]";return s;}
}
namespace Util { struct SaveQueue {std::string bytes; static SaveQueue& Get(){static SaveQueue q;return q;}void Submit(const char*,std::string s){bytes=std::move(s);} }; }
namespace RE {
using FormID=uint32_t;
struct BGSKeywordForm {bool ContainsKeywordString(const char*)const{return false;}};
struct TESForm {FormID formID;template<class T>T* As(){return nullptr;}};
struct File {std::string fileName="Loaded.esp";};
struct TESDataHandler {
    File file;
    static TESDataHandler* GetSingleton(){static TESDataHandler h;return &h;}
    File* LookupModByName(const std::string& s){return s==file.fileName?&file:nullptr;}
    FormID LookupFormID(uint32_t id,const std::string&){return 0x01000000|id;}
    File* LookupLoadedModByIndex(uint8_t i){return i==1?&file:nullptr;}
    File* LookupLoadedLightModByIndex(uint16_t){return nullptr;}
};
}
'''+header+source+r'''
int main(){
    using namespace UserData;
    RE::TESForm a{0x01000001}, b{0x01000002};
    YAML::input["Loaded.esp"][1]=1;
    YAML::input["Loaded.esp"][2]=-1;
    YAML::input["Absent.esp"][7]=1;
    StripData strips;strips.Load();assert(strips.CheckStrip(&a)==Strip::Always);
    strips.RemoveArmor(&a);strips.Save();
    assert(Util::SaveQueue::Get().bytes=="[Absent.esp:[7:1]][Loaded.esp:[2:-1]]");
    strips.RemoveArmorAll();strips.Save();
    assert(Util::SaveQueue::Get().bytes=="[Absent.esp:[7:1]]");
    strips.AddArmor(&b,Strip::Always);strips.Save();
    assert(Util::SaveQueue::Get().bytes=="[Absent.esp:[7:1]][Loaded.esp:[2:1]]");
    YAML::input=YAML::Node{};strips.Load();assert(strips.CheckStrip(&b)==Strip::None);
    strips.AddArmor(&a,Strip::Always);
    YAML::input["Loaded.esp"][2].scalar="bad integer";
    strips.Load();assert(strips.CheckStrip(&a)==Strip::Always);assert(strips.CheckStrip(&b)==Strip::None);
    std::cout<<"PASS: production strip deletion/reset, unavailable plugin preservation and atomic reload\n";
}
'''
# CheckKeywords uses a reference to a temporary pointer in the engine API; the
# stand-in returns a pointer by reference to match that call convention.
code=code.replace('template<class T>T* As(){return nullptr;}','template<class T>T*& As(){static T* value=nullptr;return value;}')
run('strip',code)
