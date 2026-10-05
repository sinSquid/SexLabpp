"""Production legacy-statistics conversion and tracked-actor ordering regressions."""
import os
import subprocess

from source_regressions import ROOT, function, run


def source(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(
            ['git', 'show', f"{os.environ['REVIEW_BASE']}:{path}"],
            cwd=ROOT, text=True)
    return (ROOT / path).read_text()


production = source('src/Papyrus/sslActorStats.cpp')
legacy_enum = function(source('src/Papyrus/sslActorStats.h'), 'enum class LegacyStatistics')
stat_enum = function(source('src/Registry/Stats.h'), 'enum StatisticID')
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstring>
#include <format>
#include <iostream>
#include <map>
#include <optional>
#include <string>
#include <vector>
using StackID = unsigned;
struct VM { void TraceStack(const char*, StackID) {} };
struct Settings { static inline float fPercentageHomo=9, fPercentageHetero=80; };
namespace RE {
    struct StaticFunctionTag {};
    using BSFixedString=std::string;
    struct ActorBase { bool unique=true; bool IsUnique() const { return unique; } };
    struct Actor {
        unsigned id{}; bool player=false; bool hasBase=true; std::string name; ActorBase base;
        bool IsPlayerRef() const { return player; }
        ActorBase* GetActorBase() { return hasBase ? &base : nullptr; }
        const char* GetDisplayFullName() const { return name.c_str(); }
    };
    struct PlayerCharacter {
        static Actor* GetSingleton() { static Actor player{20, true, true, "Player"}; return &player; }
    };
    struct Calendar {
        static Calendar* GetSingleton() { static Calendar instance; return &instance; }
        float GetTimescale() const { return 20; }
    };
}
namespace Registry {
    enum class Sex { Male=1, Female=2 };
    struct RaceKey { enum Value { Human }; bool Is(Value) const { return true; } };
    namespace Statistics {
        struct ActorStats {
''' + stat_enum + r''';
            std::array<float, Total> values{};
            std::map<std::string, float> custom;
            float GetStatistic(StatisticID id) const { return values[id]; }
            void SetStatistic(StatisticID id, float value) { values[id]=value; }
            std::optional<float> GetCustomFlt(const char* key) const {
                auto it=custom.find(key); return it==custom.end() ? std::nullopt : std::optional(it->second);
            }
            void SetCustomFlt(const char* key, float value) { custom[key]=value; }
        };
        struct StatisticsData {
            ActorStats stats;
            std::vector<RE::Actor*> tracked;
            struct Encounter { unsigned id{}; Sex sex{}; RaceKey race; };
            static StatisticsData* GetSingleton() { static StatisticsData instance; return &instance; }
            mutable int snapshots=0;
            ActorStats GetStatisticsSnapshot(RE::Actor*) const { ++snapshots;return stats; }
            ActorStats* GetStatistics(RE::Actor*) { return &stats; }
            std::vector<RE::Actor*> GetTrackedActors() const { return tracked; }
            template<class T> int GetNumberEncounters(RE::Actor*, T predicate) { Encounter value; return predicate(value); }
        };
    }
}
namespace Papyrus::ActorStats {
inline constexpr auto Purity="Purity", Lewdness="Lewdness", Foreplay="Foreplay";
''' + legacy_enum + ';\n'
if 'float GetLegacyStatisticFromSnapshot(' in production:
    code += function(production, 'float GetLegacyStatisticFromSnapshot(') + '\n'
for signature in ('std::vector<float> GetAllLegycSkills(', 'float GetLegacyStatistic(', 'void SetLegacyStatistic(',
                  'std::vector<RE::Actor*> GetAllTrackedUniqueActorsSorted('):
    code += function(production, signature) + '\n'
code += '}\n'
code += 'const auto actorLess = ' + function(production, '[](RE::Actor* a, RE::Actor* b)') + ';\n'
code += r'''
int main() {
    using namespace Papyrus::ActorStats;
    using Stats=Registry::Statistics::ActorStats;
    auto* data=Registry::Statistics::StatisticsData::GetSingleton();
    auto* actor=RE::PlayerCharacter::GetSingleton();
    VM vm;
    auto all=GetAllLegycSkills(&vm,0,nullptr,actor);
    assert(data->snapshots==1 && all.size()==static_cast<size_t>(LegacyStatistics::Total));
    for(size_t i=0;i<all.size();++i) assert(all[i]==GetLegacyStatistic(&vm,0,nullptr,actor,static_cast<int>(i)));
    const auto snapshots=data->snapshots;
    all=GetAllLegycSkills(&vm,0,nullptr,nullptr);assert(data->snapshots==snapshots);
    assert(std::all_of(all.begin(),all.end(),[](float value){return value==0;}));
    const auto get=[&] { return GetLegacyStatistic(&vm,0,nullptr,actor,int(LegacyStatistics::Sexuality)); };
    const auto set=[&](float value) { SetLegacyStatistic(&vm,0,nullptr,actor,int(LegacyStatistics::Sexuality),value); };
    data->stats.SetStatistic(Stats::Sexuality,30);
    assert(std::abs(get()-69.375f)<0.0001f);
    const std::array<std::array<float,2>,8> distributions{{
        {80,9},{30,20},{0,50},{50,0},{90,10},{100,0},{0,100},{0,0}
    }};
    for (const auto& distribution : distributions) {
        Settings::fPercentageHetero=distribution[0];
        Settings::fPercentageHomo=distribution[1];
        float previous=-1;
        for (int index=0;index<=1000;++index) {
            const auto native=index/10.0f;
            data->stats.SetStatistic(Stats::Sexuality,native);
            const auto legacy=get();
            assert(std::isfinite(legacy) && legacy>=0 && legacy<=100.0001f);
            assert(legacy>=previous); previous=legacy;
            set(legacy);
            assert(std::abs(data->stats.GetStatistic(Stats::Sexuality)-native)<0.0001f);
        }
        // A collapsed category cannot retain every legacy value; verify its
        // canonical native boundary separately rather than claiming bijection.
        if (distribution[0]>0 && distribution[1]>0 && distribution[0]+distribution[1]<100) {
            for (int index=0;index<=1000;++index) {
                const auto legacy=index/10.0f; set(legacy);
                assert(std::abs(get()-legacy)<0.0001f);
            }
        }
    }
    Settings::fPercentageHetero=90; Settings::fPercentageHomo=10;
    for (float value : {35.0f,50.0f,65.0f}) {
        set(value); assert(data->stats.GetStatistic(Stats::Sexuality)==10);
        assert(get()==65);
    }
    Settings::fPercentageHetero=0; Settings::fPercentageHomo=100;
    set(100); assert(get()==100);

    RE::Actor amy{1,false,true,"Amy"}, zoe{2,false,true,"Zoe"};
    RE::Actor duplicateName{3,false,true,"Amy"}, generic{4,false,true,"Generic"};
    RE::Actor noBase{5,false,false,"Missing"}; generic.base.unique=false;
    const std::vector<RE::Actor*> actors{actor,&amy,&zoe,&duplicateName};
    for (auto a:actors) {
        assert(!actorLess(a,a));
        for (auto b:actors) {
            assert(!(actorLess(a,b) && actorLess(b,a)));
            for (auto c:actors) if(actorLess(a,b) && actorLess(b,c)) assert(actorLess(a,c));
        }
    }
    data->tracked={&zoe,&generic,&amy,actor,&noBase,&duplicateName};
    const auto sorted=GetAllTrackedUniqueActorsSorted(nullptr);
    assert(sorted.size()==4 && sorted.front()==actor && sorted.back()==&zoe);
    assert(sorted[1]->name=="Amy" && sorted[2]->name=="Amy");
    data->tracked={&generic,&noBase};
    assert(GetAllTrackedUniqueActorsSorted(nullptr)==std::vector<RE::Actor*>{actor});
    std::cout<<"PASS: production legacy statistics round trips, collapsed ranges and strict actor ordering\n";
}
'''
run('full6_persistence', code)
