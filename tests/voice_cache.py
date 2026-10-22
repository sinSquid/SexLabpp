from statistics_roundtrip import ROOT, function, run

code=r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <thread>
#include <vector>
namespace logger {template<class...T>void error(T&&...) {}}
namespace RE {
 namespace SEXES {enum SEX{kNone=-1,kMale=0,kFemale=1};}
 struct VoiceType {uint32_t formID=9;};
 struct Base {VoiceType* voice=nullptr;SEXES::SEX GetSex(){return SEXES::kMale;}VoiceType* GetVoiceType(){return voice;}};
 struct Actor {uint32_t formID;Base* base;uint32_t GetFormID(){return formID;}Base* GetActorBase(){return base;}};
}
struct RaceKey {RaceKey(RE::Actor*){}bool IsValid()const{return true;}};
struct TagDetails {bool MatchTags(int)const{return true;}};
enum class Pitch {Unknown,Normal,High,Low};
struct Voice {bool enabled=true;RE::SEXES::SEX sex=RE::SEXES::kMale;int tags=0;Pitch pitch=Pitch::Normal;bool HasRace(RaceKey)const{return true;}};
struct VoicePitch {Pitch pitch;const Voice* voice;};
struct Expression {bool enabled=true;bool IsEnabled()const{return enabled;}int GetTags()const{return 0;}};
struct Random {static inline std::atomic<int> draws=0;template<class T>static auto draw(const T& v){++draws;return v.front();}};
struct Library {
 mutable std::shared_mutex _mVoice,_mExpressions;
 std::map<uint32_t,const Voice*> savedVoices;
 std::map<std::string,Voice> voices;
 std::map<uint32_t,VoicePitch> savedPitches;
 std::map<std::string,Expression> expressions;
 const Voice* GetVoice(RE::Actor*,const TagDetails&);
 const Voice* GetVoice(const TagDetails&)const;
 const Voice* GetVoice(RaceKey)const;
 const Expression* GetExpression(const TagDetails&)const;
};
'''
code += function((ROOT/'src/Registry/Library.cpp').read_text(),'const Voice* Library::GetVoice(RE::Actor*')
for signature in ('const Voice* Library::GetVoice(const TagDetails&', 'const Voice* Library::GetVoice(RaceKey', 'const Expression* Library::GetExpression(const TagDetails&'):
 code += function((ROOT/'src/Registry/Library.cpp').read_text(),signature)
code += r'''
int main(){
 Library lib;RE::VoiceType type;RE::Base base{&type};RE::Actor actor{1,&base},invalid{2,nullptr};
 lib.voices["a"].pitch=Pitch::Low;lib.voices["b"].pitch=Pitch::High;
 lib.savedPitches[9]={Pitch::High,nullptr};
 assert(lib.GetVoice(nullptr,{})==nullptr&&lib.GetVoice(&invalid,{})==nullptr);
 std::vector<std::thread> threads;std::vector<const Voice*> results(8);
 for(int i=0;i<8;++i)threads.emplace_back([&,i](){results[i]=lib.GetVoice(&actor,{});});
 for(auto& t:threads)t.join();
 assert(Random::draws==1);for(auto* v:results)assert(v==&lib.voices.at("b"));
 lib.savedVoices.clear();lib.savedPitches[9]={Pitch::Normal,nullptr};
 assert(lib.GetVoice(&actor,{})==&lib.voices.at("a"));
 lib.voices["a"].enabled=false;lib.voices["b"].enabled=false;
 assert(!lib.GetVoice(TagDetails{})&&!lib.GetVoice(RaceKey{&actor}));
 lib.voices["b"].enabled=true;assert(lib.GetVoice(TagDetails{})==&lib.voices.at("b"));
 lib.expressions["a"].enabled=false;assert(!lib.GetExpression({}));
 lib.expressions["b"].enabled=true;assert(lib.GetExpression({})==&lib.expressions.at("b"));
}
'''
if __name__=='__main__': run('voice_cache',code)
