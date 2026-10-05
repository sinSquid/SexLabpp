"""Actual CreateVoice/file-stem helper with fixed-string/voice stand-ins."""
import os
import subprocess
from source_regressions import ROOT, function, run

path='src/Registry/Library.cpp'
source=(subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
        if os.getenv('REVIEW_BASE') else (ROOT/path).read_text())
code=r'''
#include <cassert>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <string_view>
namespace RE {struct BSFixedString {
 std::string value;
 BSFixedString(const char* text=""):value(text){}
 bool empty()const{return value.empty();}
 const char* c_str()const{return empty()?nullptr:value.c_str();}
 bool operator<(const BSFixedString& other)const{return value<other.value;}
};}
namespace logger {template<class...T> void error(T&&...) {}}
namespace Util {
''' + function((ROOT/'src/Util/StringUtil.h').read_text(),'constexpr bool IsSafeFileStem(') + r'''
}
namespace Registry {
struct Voice {explicit Voice(RE::BSFixedString){}};
struct Library {
 std::shared_mutex _mVoice;
 std::map<RE::BSFixedString,Voice> voices;
 bool CreateVoice(RE::BSFixedString);
};
''' + function(source,'bool Library::CreateVoice(') + r'''
}
int main() {
 Registry::Library library;
 for(const char* id:{"", ".", "..", "../outside", "C:outside", "bad?name", "bad*name", "bad\nname", "CON", "nul.txt", "LPT9"}) {
  assert(!library.CreateVoice(id));assert(library.voices.empty());
 }
 for(const char* id:{"Normal Voice","名字","name.","name ","COM10"}) {
  assert(library.CreateVoice(id));assert(!library.CreateVoice(id));
 }
 assert(library.voices.size()==5);
}
'''
run('voice_creation_boundaries',code)
print('PASS: actual voice creation rejects unsafe IDs before insertion and preserves valid/duplicate behavior')
