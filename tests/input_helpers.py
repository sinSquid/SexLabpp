"""Execute audited native input helpers, including signed and missing-input cases."""
from statistics_roundtrip import ROOT, function, run

code = r'''
#include <algorithm>
#include <cassert>
#include <charconv>
#include <cstdint>
#include <memory>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
namespace logger {template<class... T>void error(T&&...) {}}
namespace RE {
 using BSFixedString=std::string;using FormID=uint32_t;
 struct StaticFunctionTag {};
 struct TESDataHandler {
  static TESDataHandler* GetSingleton(){static TESDataHandler v;return &v;}
  FormID LookupFormID(FormID id,std::string_view name){return name=="test.esp"?(0x1000000|id):0;}
 };
}
'''
source=(ROOT/'src/Papyrus/SexLabUtil.cpp').read_text()
for sig in ('int IntMinMaxIndex(', 'int IntMinMaxValue(', 'int FloatMinMaxIndex(', 'float FloatMinMaxValue('):
    code += function(source,sig)
code += function((ROOT/'src/Util/FormLookup.h').read_text(),'static inline RE::FormID FormFromString(const std::string_view& a_string, int base)')
code += r'''
enum class RawType {kBool,kInt,kFloat,kOther};
struct Variable {double value=5;struct Type {RawType GetRawType(){return RawType::kFloat;}};Type GetType(){return {};}};
struct Object {Variable value;Variable* GetProperty(const std::string& key){return key=="present"?&value:nullptr;}};
using ObjectPtr=std::shared_ptr<Object>;
namespace RE::BSScript {
 template<class T>T UnpackValue(Variable* v){return static_cast<T>(v->value);}
 template<class T>void PackValue(Variable* v,T value){v->value=static_cast<double>(value);}
}
'''
source=(ROOT/'src/Util/Script.h').read_text()
for sig in ('inline T GetProperty(', 'inline T GetTrivialProperty(', 'inline void SetProperty('):
    code += '\ntemplate<class T>\n'+function(source,sig)
code += r'''
int main(){
 assert(IntMinMaxIndex(nullptr,{-9,-1,-4},true)==1);
 assert(IntMinMaxIndex(nullptr,{9,1,4},false)==1);
 assert(IntMinMaxValue(nullptr,{-9,-1,-4},true)==-1);
 assert(FloatMinMaxIndex(nullptr,{-9.f,-1.f,-4.f},true)==1);
 assert(FloatMinMaxValue(nullptr,{9.f,1.f,4.f},false)==1.f);
 assert(IntMinMaxIndex(nullptr,{},true)==0);
 assert(IntMinMaxIndex(nullptr,{1,1},false)==0);
 assert(FormFromString("0x123|test.esp",16)==0x1000123);
 assert(FormFromString("123",10)==123);
 for(auto s:{"","0x","123junk","|test.esp","-1"})assert(FormFromString(s,10)==0);
 assert(FormFromString("123",1)==0&&FormFromString("123",37)==0);
 assert(GetProperty<int>(nullptr,"present")==0);
 assert(GetTrivialProperty<float>(nullptr,"present")==0);
 auto obj=std::make_shared<Object>();
 assert(GetProperty<int>(obj,"missing")==0&&GetTrivialProperty<float>(obj,"missing")==0);
 SetProperty(obj,"missing",7);assert(obj->value.value==5);
 SetProperty(obj,"present",7);assert(GetProperty<int>(obj,"present")==7);
}
'''

if __name__=='__main__':
    run('input_helpers',code)
