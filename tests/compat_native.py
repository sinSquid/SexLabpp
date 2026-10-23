"""Production race-array and expression update/tag compatibility regressions."""
import re
from source_regressions import ROOT, function, run

registry=(ROOT/'src/Papyrus/SexLabRegistry.cpp').read_text()
code=r'''
#include <cassert>
#include <cstdint>
#include <format>
#include <string>
#include <vector>
using StackID=int;
struct VM {int errors=0;void TraceStack(const char*,int){++errors;}};
namespace RE {struct StaticFunctionTag{};using BSFixedString=std::string;struct Actor {int key;int formID=7;};}
#define STATICARGS [[maybe_unused]] VM* a_vm, [[maybe_unused]] StackID a_stackID, RE::StaticFunctionTag*
namespace Registry {
struct RaceKey {
 enum Value:uint8_t {Human=0,Other=1,Alternate=2,None=255};Value value=None;
 RaceKey(Value key):value(key){} RaceKey(RE::Actor* actor):value(Value(actor->key)){}
 RaceKey(const std::string& key):value(key=="Human"?Human:key=="Other"?Other:None){}
 bool IsValid()const{return value!=None;}
 RaceKey GetMetaRace()const{return value==Other?Alternate:None;}
 operator Value()const{return value;}
};
}
'''
for sig in ('int32_t GetRaceID(', 'int32_t MapRaceKeyToID(',
            'std::vector<int32_t> GetRaceIDA(', 'std::vector<int32_t> MapRaceKeyToIDA('):
    code+=function(registry,sig)+'\n'
code+=r'''
int main(){
 VM vm;RE::Actor human{0},other{1},invalid{255};
 assert(GetRaceIDA(&vm,0,nullptr,&human)==std::vector<int32_t>{0});
 assert(MapRaceKeyToIDA(&vm,0,nullptr,"Human")==std::vector<int32_t>{0});
 assert((GetRaceIDA(&vm,0,nullptr,&other)==std::vector<int32_t>{1,2}));
 assert((MapRaceKeyToIDA(&vm,0,nullptr,"Other")==std::vector<int32_t>{1,2}));
 assert(GetRaceIDA(&vm,0,nullptr,nullptr).empty());
 assert(GetRaceIDA(&vm,0,nullptr,&invalid).empty());
 assert(MapRaceKeyToIDA(&vm,0,nullptr,"unknown").empty());
 assert(GetRaceID(&vm,0,nullptr,&human)==0&&GetRaceID(&vm,0,nullptr,&invalid)==0);
 assert(MapRaceKeyToID(&vm,0,nullptr,"Human")==0&&MapRaceKeyToID(&vm,0,nullptr,"unknown")==0);
}
'''
run('compat_race_arrays',code)

expr=(ROOT/'src/Registry/Define/Expression.cpp').read_text()
header=(ROOT/'src/Registry/Define/Expression.h').read_text()
limit=re.search(r'MAX_AUTOMATIC_LEVELS\s*=\s*(\d+)',header)[1]
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <climits>
#include <map>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <vector>
bool failAllocation=false;
template<class T> struct Allocator:std::allocator<T> {
 template<class U>struct rebind{using other=Allocator<U>;};
 T* allocate(size_t n){if(failAllocation)throw std::bad_alloc();return std::allocator<T>::allocate(n);}
};
namespace RE {using BSFixedString=std::string;}
namespace logger {template<class...T>void error(T&&...) {}}
struct Expression {
 static constexpr size_t Total=32;
 static constexpr size_t MAX_AUTOMATIC_LEVELS=LIMIT;
 bool has_edits=false;
 std::vector<std::array<float,Total>,Allocator<std::array<float,Total>>> data[2];
 bool UpdateValues(bool,int,std::vector<float>);
};
struct Library {
 std::shared_mutex _mExpressions;
 std::map<std::string,Expression> expressions;
 bool UpdateExpressionValues(RE::BSFixedString,bool,int,std::vector<float>);
};
'''.replace('LIMIT',limit)
code+=function(expr,'bool Expression::UpdateValues(')
code+=function((ROOT/'src/Registry/Library.cpp').read_text(),'bool Library::UpdateExpressionValues(')
code+=r'''
int main(){
 Expression e;const auto values=std::vector<float>(32,.5f);
 assert(!e.UpdateValues(false,-1,values)&&!e.has_edits);
 assert(!e.UpdateValues(false,0,std::vector<float>(31)));
 assert(!e.UpdateValues(false,0,std::vector<float>(33)));
 assert(!e.UpdateValues(false,4096,values)&&e.data[0].empty());
 assert(!e.UpdateValues(false,INT_MAX,values)&&!e.has_edits);
 assert(e.UpdateValues(false,4095,values)&&e.data[0].size()==4096);
 assert(e.data[0][0][0]==0&&e.data[0][4095][31]==.5f&&e.data[1].empty());
 e.data[1].resize(5000);assert(e.UpdateValues(true,4999,values));
 assert(e.UpdateValues(true,4096,values));assert(!e.UpdateValues(true,5000,values));
 assert(e.has_edits&&e.data[1].size()==5000);
 Library lib;auto& item=lib.expressions["a"];
 assert(item.UpdateValues(false,0,values));item.has_edits=false;
 failAllocation=true;
 assert(!lib.UpdateExpressionValues("a",false,2000,values));
 failAllocation=false;
 assert(item.data[0].size()==1&&item.data[0][0][0]==.5f&&!item.has_edits);
 assert(!lib.UpdateExpressionValues("missing",false,0,values));
}
'''
run('compat_expression_growth',code)

block=function(expr, 'if (source.integers)')
code=r'''
#include <cassert>
#include <map>
#include <optional>
#include <set>
#include <string>
struct Tags {std::set<std::string> values;void AddTag(std::string s){values.insert(s);}};
struct Expression {bool enabled=true;Tags tags;};
Expression load(std::optional<std::map<std::string,int>> values){
 struct {decltype(values) integers;} source{values};Expression expression;
'''+block+r'''
 return expression;
}
int main(){
 for(int canonical=-1;canonical<=1;++canonical)for(int legacy=-1;legacy<=1;++legacy){
  std::map<std::string,int> keys;
  if(canonical>=0)keys["victim"]=canonical;
  if(legacy>=0)keys["victim "]=legacy;
  auto e=load(keys);
  assert(e.tags.values.contains("Victim")==bool(canonical==1||legacy==1));
  assert(!e.tags.values.contains("victim "));
  assert(e.tags.values.size()==size_t(canonical==1||legacy==1));
 }
 assert(load(std::nullopt).tags.values.empty());
}
'''
run('compat_legacy_tag_aliases',code)
