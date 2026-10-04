"""Partner selection regressions using extracted production native functions."""
import os
from pathlib import Path
from source_regressions import ROOT, function, run

root = Path(os.environ.get('REVIEW_BASE_DIR', ROOT))
production = (root / 'src/Papyrus/sslLibrary/sslThreadLibrary.cpp').read_text()
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
#include <vector>
struct VM {int errors{};void TraceStack(const char*,int){++errors;}};
using StackID=int;
enum LegacySex{Male=0,Female=1,CrtMale=2,CrtFemale=3,None=-1};
namespace RE {
 struct Actor{int id;LegacySex sex;};using TESObjectREFR=Actor;struct TESQuest{};using BSFixedString=std::string;
 struct PlayerCharacter{static Actor* GetSingleton(){static Actor a{0,Male};return &a;}};
}
std::vector<RE::Actor*> available;
int searches=0;
std::vector<RE::Actor*> FindAvailableActors(VM*,int,RE::TESQuest*,RE::TESObjectREFR*,float,LegacySex,
 RE::Actor* a,RE::Actor* b,RE::Actor* c,RE::Actor* d,RE::BSFixedString){
 ++searches;auto result=available;
 std::erase_if(result,[&](auto actor){return actor==a||actor==b||actor==c||actor==d;});return result;
}
LegacySex GetLegacySex(RE::Actor* a){assert(a);return a->sex;}
std::array<int32_t,4> GetLegacySex(std::vector<RE::Actor*> actors){
 std::array<int32_t,4> result{};for(auto* a:actors)++result[GetLegacySex(a)];return result;
}
'''
code += function(production, 'std::vector<RE::Actor*> FindAvailablePartners(')
code += r'''
int main(){
 VM vm;RE::Actor f1{1,Female},f2{2,Female},m1{3,Male},m2{4,Male},m3{5,Male};
 available={&f1,&m1};
 auto result=FindAvailablePartners(&vm,0,nullptr,{},2,1,1,100);
 assert(result.size()==2);auto count=GetLegacySex(result);assert(count[Male]==1&&count[Female]==1);
 // Feasible required counts must not depend on process-list iteration order.
 available={&f1,&f2,&m1,&m2};
 std::sort(available.begin(),available.end(),[](auto a,auto b){return a->id<b->id;});
 do{
  result=FindAvailablePartners(&vm,0,nullptr,{},4,1,1,100);
  assert(result.size()==4);count=GetLegacySex(result);assert(count[Male]>=1&&count[Female]>=1);
 }while(std::next_permutation(available.begin(),available.end(),[](auto a,auto b){return a->id<b->id;}));
 available={&f1,&f2,&m1,&m2};
 result=FindAvailablePartners(&vm,0,nullptr,{&m1},3,1,1,100);
 assert(result.size()==3&&result.front()==&m1);
 assert(std::count(result.begin(),result.end(),&m1)==1);
 // Do not fill required-but-unavailable gender slots with an unrelated actor.
 available={&m1,&m2};result=FindAvailablePartners(&vm,0,nullptr,{},2,1,1,100);
 assert(result.size()==1&&result.front()==&m1);
 available={&f1,&m1,&m2};result=FindAvailablePartners(&vm,0,nullptr,{},2,-1,-1,100);
 assert((result==std::vector<RE::Actor*>{&f1,&m1}));
 // Existing vectors longer than the four ignore slots must not add duplicates.
 available={&f1,&f2,&m1,&m2,&m3};
 result=FindAvailablePartners(&vm,0,nullptr,{&f1,&f2,&m1,&m2,&m3},6,-1,-1,100);
 assert(result.size()==5);
 searches=0;result=FindAvailablePartners(&vm,0,nullptr,{&f1},-1,-1,-1,100);
 assert((result==std::vector<RE::Actor*>{&f1})&&searches==0);
 result=FindAvailablePartners(&vm,0,nullptr,{},0,-1,-1,100);assert(result.empty()&&searches==0);
 result=FindAvailablePartners(&vm,0,nullptr,{&f1,nullptr},3,-1,-1,100);
 assert(result.empty()&&vm.errors==1&&searches==0);
 result=FindAvailablePartners(&vm,0,nullptr,{&f1,&f1},3,-1,-1,100);
 assert(result.empty()&&vm.errors==2&&searches==0);
 std::cout<<"PASS: order-independent partner requirements, remaining capacity, unique inputs and invalid totals\n";
}
'''
run('full7_partner_selection', code)
