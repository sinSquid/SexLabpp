"""Production Papyrus query regressions with engine/VM stand-ins."""
import os
import subprocess
from source_regressions import ROOT, function, run


def source(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git', 'show', f"{os.environ['REVIEW_BASE']}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


def legacy_queries():
    production = source('src/Papyrus/sslThreadModel.cpp')
    code = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <memory>
#include <set>
#include <vector>
struct VM {void TraceStack(const char*,int){}};
namespace RE {struct Actor {uint32_t formID;};struct TESQuest{};}
struct Interaction {
 std::shared_ptr<RE::Actor> partner;int action;
 bool operator<(const Interaction& rhs)const {
  return partner->formID==rhs.partner->formID?action<rhs.action:partner->formID<rhs.partner->formID;
 }
};
struct Position {std::shared_ptr<RE::Actor> actor;std::set<Interaction> interactions;};
struct Legacy {
 std::vector<Position> positions;
 template<class F> bool VisitPositions(F f){for(auto& p:positions)if(f(p))return true;return false;}
};
struct Instance {Legacy* ni{};Legacy* GetNiInstanceLegacy(){return ni;}};
Instance* current{};
#define QUESTARGS VM* a_vm, int a_stackID, RE::TESQuest* a_qst
#define GET_INSTANCE(ret) auto instance=current;if(!instance)return ret
'''
    for sig in ('RE::Actor* GetPartnerByActionRevLegacy(', 'std::vector<RE::Actor*> GetPartnersByActionRevLegacy('):
        code += function(production, sig) + '\n'
    code += r'''
int main(){
 VM vm;RE::TESQuest quest;
 auto a=std::make_shared<RE::Actor>(RE::Actor{1});auto b=std::make_shared<RE::Actor>(RE::Actor{2});
 auto c=std::make_shared<RE::Actor>(RE::Actor{3});auto target=std::make_shared<RE::Actor>(RE::Actor{4});
 // The engine can emit Oral (3) and Deepthroat (5) for the same partner.
 Legacy legacy{{{a,{{target,3},{target,5}}},{b,{{c,1},{target,5}}}}};Instance inst{&legacy};current=&inst;
 assert(GetPartnerByActionRevLegacy(&vm,0,&quest,target.get(),5)==a.get());
 assert((GetPartnersByActionRevLegacy(&vm,0,&quest,target.get(),5)==std::vector<RE::Actor*>{a.get(),b.get()}));
 assert((GetPartnersByActionRevLegacy(&vm,0,&quest,nullptr,5)==std::vector<RE::Actor*>{a.get(),b.get()}));
 // Wildcards still yield each matching source actor once, and no match stays empty.
 assert((GetPartnersByActionRevLegacy(&vm,0,&quest,nullptr,-1)==std::vector<RE::Actor*>{a.get(),b.get()}));
 assert(GetPartnersByActionRevLegacy(&vm,0,&quest,target.get(),99).empty());
 assert(GetPartnerByActionRevLegacy(&vm,0,&quest,target.get(),99)==nullptr);
 assert(GetPartnerByActionRevLegacy(&vm,0,&quest,nullptr,5)==nullptr);
 inst.ni=nullptr;assert(GetPartnersByActionRevLegacy(&vm,0,&quest,target.get(),5).empty());
 current=nullptr;assert(GetPartnerByActionRevLegacy(&vm,0,&quest,target.get(),5)==nullptr);
 std::cout<<"PASS: legacy reverse queries scan every action and deduplicate matching source actors\n";
}
'''
    run('full6_legacy_queries', code)


def registry_queries():
    production = source('src/Papyrus/SexLabRegistry.cpp')
    code = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
struct VM {std::vector<std::string> errors;void TraceStack(const char* s,int){errors.emplace_back(s);}};
using StackID=int;
namespace RE {struct StaticFunctionTag{};using BSFixedString=std::string;}
struct Offset {int resets{};void ResetOffset(){++resets;}};
struct Position {bool climax{};Offset offset;};
struct Stage {RE::BSFixedString id;std::vector<Position> positions;};
struct Scene {
 std::vector<Position> positions{{},{}};std::vector<Stage> stages{{"one",{{true},{false}}},{"two",{{false},{true}}}};
 std::vector<const Stage*> GetClimaxStages()const{std::vector<const Stage*> out;for(const auto& s:stages)out.push_back(&s);return out;}
 Stage* GetStageByID(RE::BSFixedString id){for(auto& s:stages)if(s.id==id)return &s;return nullptr;}
};
Scene state;
namespace Registry {struct Library {
 static Library* GetSingleton(){static Library lib;return &lib;}
 Scene* GetSceneById(RE::BSFixedString id){return id=="scene"?&state:nullptr;}
 template<class F> bool EditScene(RE::BSFixedString id,F f){if(auto* s=GetSceneById(id)){f(s);return true;}return false;}
};}
#define STATICARGS VM* a_vm, StackID a_stackID, RE::StaticFunctionTag*
'''
    start = production.index('#define SCENE(')
    end = production.index('    int32_t GetRaceID(', start)
    code += production[start:end]
    for sig in ('std::vector<RE::BSFixedString> GetClimaxStages(', 'void ResetStageOffset('):
        code += function(production, sig) + '\n'
    code += r'''
int main(){
 VM vm;
 assert((GetClimaxStages(&vm,0,nullptr,"scene",-1)==std::vector<std::string>{"one","two"}));
 assert((GetClimaxStages(&vm,0,nullptr,"scene",0)==std::vector<std::string>{"one"}));
 assert((GetClimaxStages(&vm,0,nullptr,"scene",1)==std::vector<std::string>{"two"}));
 assert(vm.errors.empty());
 for(auto n:{-2,std::numeric_limits<int32_t>::min(),2,std::numeric_limits<int32_t>::max()}){
  vm.errors.clear();assert(GetClimaxStages(&vm,0,nullptr,"scene",n).empty());assert(vm.errors.size()==1);
 }
 vm.errors.clear();ResetStageOffset(&vm,0,nullptr,"scene","one",0);
 assert(state.stages[0].positions[0].offset.resets==1);assert(vm.errors.empty());
 ResetStageOffset(&vm,0,nullptr,"missing","one",0);assert(vm.errors.size()==1);
 vm.errors.clear();ResetStageOffset(&vm,0,nullptr,"scene","missing",0);assert(vm.errors.size()==1);
 vm.errors.clear();ResetStageOffset(&vm,0,nullptr,"scene","one",-1);assert(vm.errors.size()==1);
 assert(state.stages[0].positions[0].offset.resets==1);
 std::cout<<"PASS: climax wildcard/bounds and stage-reset success/error reporting\n";
}
'''
    run('full6_registry_queries', code)


if os.getenv('REVIEW_CASE', 'all') in ('all', 'legacy'):
    legacy_queries()
if os.getenv('REVIEW_CASE', 'all') in ('all', 'registry'):
    registry_queries()
