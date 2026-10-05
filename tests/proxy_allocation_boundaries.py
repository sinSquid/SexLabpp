"""Actual proxy query allocation behavior; fixture allocator refuses > 1 MiB."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Papyrus/sslObject/sslAnimationSlots.cpp').read_text()
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <limits>
#include <new>
#include <string>
#include <vector>
void* operator new(size_t n){if(n>1024*1024)throw std::bad_alloc();if(void* p=std::malloc(n?n:1))return p;throw std::bad_alloc();}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete(void* p,size_t)noexcept{std::free(p);}
namespace RE {struct StaticFunctionTag{};using BSFixedString=std::string;}
namespace Registry {
struct TagDetails {TagDetails(const std::string&){} };
struct Scene {std::string id,name;bool HasCreatures()const{return false;}std::string GetPackageHash()const{return "hash";}bool IsCompatibleTags(const TagDetails&)const{return true;}};
struct AnimPackage {std::string GetName()const{return "pack";}std::string GetHash()const{return "hash";} };
struct Library {
 std::vector<Scene> scenes{{"b","b"},{"a","a"}};
 static Library* GetSingleton(){static Library l;return &l;}
 size_t GetSceneCount()const{return scenes.size();}
 std::vector<std::string> GetLegacyProxyIds(size_t,uint32_t)const{return {"b","a"};}
 template<class F>void ForEachPackage(F f)const{AnimPackage p;f(&p);}
 template<class F>void ForEachScene(F f)const{for(const auto& s:scenes)if(f(&s))break;}
};
}
'''+function(source,'std::vector<RE::BSFixedString> CreateProxyArray(')+r'''
int main(){
 auto ids=CreateProxyArray(nullptr,std::numeric_limits<uint32_t>::max(),2,"tag","");
 assert((ids==std::vector<std::string>{"a","b"}));
 ids=CreateProxyArray(nullptr,1,2,"tag","");assert((ids==std::vector<std::string>{"b"}));
 ids=CreateProxyArray(nullptr,0,2,"tag","");assert(ids.size()==2);
}
'''
run('proxy_allocation_boundaries',code)
print('PASS: actual filtered proxy query handles UINT32_MAX without allocating from an untrusted limit')
