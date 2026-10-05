"""Actual script helpers with VM/property stand-ins; no Papyrus VM/ABI claim."""
import os
from pathlib import Path
from source_regressions import ROOT, function, run

source=Path(os.environ.get('SCRIPT_SOURCE',ROOT/'src/Util/Script.h')).read_text()
prefix=r'''
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
#include <type_traits>
namespace std {template<class E> constexpr auto to_underlying(E e){return static_cast<underlying_type_t<E>>(e);}}
namespace logger {template<class...T>void error(T&&...) {}}
namespace RE {
 using BSFixedString=std::string;
 struct TESForm{};
 namespace BSScript {
  enum class RawType{kBool,kInt,kFloat,kNone};
  struct Type {RawType raw;RawType GetRawType()const{return raw;}};
  struct Variable {RawType raw=RawType::kFloat;float number=0;int integer=0;bool boolean=false;Type GetType()const{return {raw};}};
  template<class T>T UnpackValue(Variable* v) {
   if constexpr(std::is_same_v<T,float>)return v->number;
   else if constexpr(std::is_same_v<T,bool>)return v->boolean;
   else return v->integer;
  }
 }
}
namespace Script {
 using RawType=RE::BSScript::RawType;
 struct Object {RE::BSScript::Variable value;bool missing=false;RE::BSScript::Variable* GetProperty(const std::string&){return missing?nullptr:&value;}};
 using ObjectPtr=Object*;
 struct VM {
  static inline Object created;
  static inline bool creationSucceeds=false;
  static inline int binds=0,lookups=0;
  static VM* GetSingleton(){static VM vm;return &vm;}
  bool FindBoundObject(int,const char*,ObjectPtr&){++lookups;return false;}
  void CreateObject2(const char*,ObjectPtr& object){object=creationSucceeds?&created:nullptr;}
  void BindObject(ObjectPtr object,int,bool){assert(object);++binds;}
 };
 int GetHandle(const RE::TESForm* form){assert(form);return 7;}
'''
code=prefix+'template<class T>\n'+function(source,'inline T GetTrivialProperty(')+r'''
}
int main() {
 Script::Object object;
 for(float invalid:{NAN,INFINITY,-INFINITY}) {
  object.value.number=invalid;
  assert(Script::GetTrivialProperty<float>(&object,"p")==0);
  assert(Script::GetTrivialProperty<int32_t>(&object,"p")==0);
  assert(!Script::GetTrivialProperty<bool>(&object,"p"));
 }
 for(float invalid:{2147483648.f,-4294967296.f,std::numeric_limits<float>::max()}) {
  object.value.number=invalid;assert(Script::GetTrivialProperty<int32_t>(&object,"p")==0);
 }
 object.value.number=std::ldexp(1.f,63);
 assert(Script::GetTrivialProperty<int64_t>(&object,"p")==0);
 object.value.number=std::ldexp(1.f,64);
 assert(Script::GetTrivialProperty<uint64_t>(&object,"p")==0);
 object.value.number=-2147483648.f;
 assert(Script::GetTrivialProperty<int32_t>(&object,"p")==INT32_MIN);
 object.value.number=2147483520.f;
 assert(Script::GetTrivialProperty<int32_t>(&object,"p")==2147483520);
 object.value.number=-1.75f;
 assert(Script::GetTrivialProperty<int32_t>(&object,"p")==-1);
 assert(Script::GetTrivialProperty<bool>(&object,"p"));
 object.value.number=-.5f;assert(Script::GetTrivialProperty<uint32_t>(&object,"p")==0);
 object.value.number=.75f;assert(Script::GetTrivialProperty<float>(&object,"p")==.75f);
 object.value.raw=Script::RawType::kInt;object.value.integer=21;
 assert(Script::GetTrivialProperty<float>(&object,"p")==21);
 object.value.raw=Script::RawType::kBool;object.value.boolean=true;
 assert(Script::GetTrivialProperty<int32_t>(&object,"p")==1);
 object.missing=true;assert(Script::GetTrivialProperty<int32_t>(&object,"p")==0);
 assert(Script::GetTrivialProperty<float>(nullptr,"p")==0);
}
'''
if os.getenv('SCRIPT_CASE','property')=='property':
    run('script_property_boundaries',code)
    print('PASS: actual property helper rejects nonfinite/out-of-range float conversions and preserves valid coercions')

code=prefix+function(source,'inline ObjectPtr GetScriptObject(')+r'''
}
int main() {
 RE::TESForm form;
 assert(!Script::GetScriptObject(&form,"Class",true));
 assert(Script::VM::binds==0);
 const int lookups=Script::VM::lookups;
 assert(!Script::GetScriptObject(nullptr,"Class",true));
 assert(!Script::GetScriptObject(&form,nullptr,true));
 assert(!Script::GetScriptObject(&form,"",true));
 assert(Script::VM::lookups==lookups);
 Script::VM::creationSucceeds=true;
 assert(Script::GetScriptObject(&form,"Class",true)==&Script::VM::created);
 assert(Script::VM::binds==1);
 assert(!Script::GetScriptObject(&form,"Class"));assert(Script::VM::binds==1);
}
'''
if os.getenv('SCRIPT_CASE','object')=='object':
    run('script_object_boundaries',code)
    print('PASS: actual object helper avoids null/empty lookups and binding failed creation')
