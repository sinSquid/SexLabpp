"""Compile actual production function bodies with small engine stand-ins.
This is not a DLL/ABI or Papyrus runtime test. No copied implementation is tested.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def run(name, code):
    with tempfile.TemporaryDirectory(prefix="sexlab-test-") as tmp:
        source = Path(tmp) / f"{name}.cpp"
        source.write_text(code)
        binary = Path(tmp) / name
        subprocess.run([os.environ.get("CXX", "clang++"), "-std=c++20", "-O1", "-pthread", "-I", str(ROOT / "src"), str(source), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


def graph_test():
    production = (ROOT / 'src/Registry/Define/Animation.cpp').read_text()
    code = r'''
#include <algorithm>
#include <cassert>
#include <functional>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <vector>
namespace logger { inline int warnings=0; template<class... T> void warn(T&&...) { ++warnings; } }
struct Stage { int id; };
struct Scene {
    enum class NodeType { None, Root, Sink, Default };
    const Stage* start_animation{};
    std::map<const Stage*, std::vector<const Stage*>> graph;
    NodeType GetStageNodeType(const Stage*) const;
    std::vector<const Stage*> GetShortestPath(const Stage*) const;
    std::vector<const Stage*> GetLongestPath(const Stage*) const;
};
'''
    for signature in ['Scene::NodeType Scene::GetStageNodeType', 'std::vector<const Stage*> Scene::GetShortestPath', 'std::vector<const Stage*> Scene::GetLongestPath']:
        code += function(production, signature) + '\n'
    code += r'''
int main() {
    Stage nodes[5]{{0},{1},{2},{3},{4}};
    for (unsigned mask = 0; mask < 1024; ++mask) {
        Scene scene; scene.start_animation = &nodes[0];
        unsigned bit = 0;
        for (int a = 0; a < 5; ++a) {
            auto& edges = scene.graph[&nodes[a]];
            for (int b = a + 1; b < 5; ++b, ++bit) if (mask & (1u << bit)) edges.push_back(&nodes[b]);
            std::reverse(edges.begin(), edges.end()); // exercise merging branches before longer routes
        }
        for (auto& node : nodes) {
            size_t shortest = 99, longest = 0;
            std::function<void(const Stage*, size_t)> visit = [&](const Stage* n, size_t length) {
                if (scene.graph[n].empty()) { shortest = std::min(shortest, length); longest = std::max(longest, length); }
                for (const auto* next : scene.graph[n]) visit(next, length + 1);
            };
            visit(&node, 1);
            assert(scene.GetShortestPath(&node).size() == shortest);
            assert(scene.GetLongestPath(&node).size() == longest);
        }
    }
    // Every directed four-node graph, including cycles: compare exact results
    // below the budget with independent exhaustive simple-path enumeration.
    for(unsigned mask=0;mask<4096;++mask) {
        Scene scene; unsigned bit=0;
        for(int a=0;a<4;++a) {
            auto& edges=scene.graph[&nodes[a]];
            for(int b=0;b<4;++b) if(a!=b) { if(mask & (1u<<bit)) edges.push_back(&nodes[b]); ++bit; }
        }
        for(int start=0;start<4;++start) {
            size_t expected=0;std::set<const Stage*> active;
            std::function<void(const Stage*)> brute=[&](const Stage* n) {
                if(!active.insert(n).second)return;
                expected=std::max(expected,active.size());
                for(auto next:scene.graph[n])brute(next);
                active.erase(n);
            };
            brute(&nodes[start]);
            const auto actual=scene.GetLongestPath(&nodes[start]);
            assert(actual.size()==expected);
            assert(std::set<const Stage*>(actual.begin(),actual.end()).size()==actual.size());
        }
    }
    Stage denseNodes[32]; Scene dense; dense.start_animation=&denseNodes[0];
    for (int a=0;a<32;++a) {
        auto& edges=dense.graph[&denseNodes[a]];
        for(int b=a+1;b<32;++b)edges.push_back(&denseNodes[b]);
    }
    assert(dense.GetLongestPath(&denseNodes[0]).size()==32);
    std::vector<Stage> chainNodes(4096); Scene chain;
    for(size_t i=0;i<chainNodes.size();++i) {
        auto& edges=chain.graph[&chainNodes[i]];
        if(i+1<chainNodes.size()) edges.push_back(&chainNodes[i+1]);
    }
    assert(chain.GetLongestPath(&chainNodes[0]).size()==4096);
    Scene parallel;
    parallel.graph={{&nodes[0],{&nodes[1],&nodes[1]}},{&nodes[1],{}},{&nodes[2],{&nodes[2]}}};
    assert(parallel.GetLongestPath(&nodes[0]).size()==2);
    Scene cyclic; cyclic.start_animation = &nodes[0];
    cyclic.graph = {{&nodes[0], {&nodes[1]}}, {&nodes[1], {&nodes[0], &nodes[2]}}, {&nodes[2], {}}};
    assert(cyclic.GetShortestPath(&nodes[0]).size() == 3);
    assert(cyclic.GetLongestPath(&nodes[0]).size() == 3);
    assert(cyclic.GetLongestPath(nullptr).empty());
    Scene hardCycle;
    for(int a=0;a<12;++a) for(int b=0;b<12;++b) if(a!=b) hardCycle.graph[&denseNodes[a]].push_back(&denseNodes[b]);
    const auto bounded=hardCycle.GetLongestPath(&denseNodes[0]);
    assert(logger::warnings==1 && bounded.size()==12);
    assert(std::set<const Stage*>(bounded.begin(),bounded.end()).size()==bounded.size());
    for(size_t i=1;i<bounded.size();++i) { const auto& edges=hardCycle.graph[bounded[i-1]]; assert(std::find(edges.begin(),edges.end(),bounded[i])!=edges.end()); }
    assert(hardCycle.GetLongestPath(&denseNodes[0])==bounded);
    std::cout << "PASS: production path functions, 1024 DAGs/all roots and cycle\n";
}
'''
    run('paths', code)


def statistics_test():
    header = (ROOT / 'src/Registry/Stats.h').read_text()
    header = re.sub(r'^#(?:include|pragma).*$', '', header, flags=re.M)
    production = (ROOT / 'src/Registry/Stats.cpp').read_text()
    production = re.sub(r'^#include.*$', '', production, flags=re.M)
    production = production.replace(function(production, 'ActorStats::ActorStats(RE::Actor* owner)'), 'ActorStats::ActorStats(RE::Actor*) : _stats(Total) {}')
    production = production.replace(function(production, 'void StatisticsData::Register()'), 'void StatisticsData::Register() {}')
    code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <ranges>
#include <shared_mutex>
#include <string>
#include <thread>
#include <variant>
#include <vector>
#include "Util/RecordIO.h"
#define __fallthrough [[fallthrough]]
namespace logger { template<class... T> void error(T&&...) {} template<class... T> void info(T&&...) {} template<class... T> void warn(T&&...) {} }
template<class T> struct Singleton { static T* GetSingleton() { static T value; return &value; } };
using FixedStringCompare = std::less<std::string>;
namespace RE {
    using BSFixedString = std::string; using FormID = uint32_t;
    enum class FormType { ActorCharacter, Other };
    struct Actor;
    inline std::map<FormID, Actor*> actors;
    struct TESForm {
        FormID formID;
        bool actorForm = true;
        bool IsNot(FormType) const { return !actorForm; }
        template<class T> static T* LookupByID(FormID id) { auto it=actors.find(id); return it==actors.end()?nullptr:it->second; }
    };
    struct Actor : TESForm { Actor(FormID id) { formID=id; actors[id]=this; } FormID GetFormID() const { return formID; } };
    struct Calendar : Singleton<Calendar> { float time=0; float GetCurrentGameTime() { return ++time; } };
    enum class BSEventNotifyControl { kContinue };
    template<class T> struct BSTEventSource {};
    template<class T> struct BSTEventSink { virtual BSEventNotifyControl ProcessEvent(const T*, BSTEventSource<T>*)=0; };
    struct TESDeathEvent { Actor* actorDying; };
    struct TESResetEvent { TESForm* object; };
}
namespace Registry {
    enum class Sex : uint8_t { Male=1 };
    struct RaceKey { enum Value:uint8_t { Human, None=255 }; Value value=None; RaceKey()=default; RaceKey(Value v):value(v){} RaceKey(RE::Actor*):value(Human){} };
    inline Sex GetSex(RE::Actor*) { return Sex::Male; }
}
namespace SKSE {
    struct SerializationInterface {
        std::vector<char> bytes; size_t pos=0;
        bool WriteRecordData(const void* data,uint32_t n) { auto p=static_cast<const char*>(data); bytes.insert(bytes.end(),p,p+n);return true; }
        uint32_t ReadRecordData(void* data,uint32_t n) { auto k=std::min<size_t>(n,bytes.size()-pos);std::memcpy(data,bytes.data()+pos,k);pos+=k;return static_cast<uint32_t>(k); }
        bool ResolveFormID(uint32_t old,uint32_t& resolved) { resolved=old;return old!=99; }
    };
}
'''
    code += header + production
    code += r'''
int main() {
    using namespace Registry::Statistics;
    RE::Actor a(1), b(2), c(3), missing(99);
    auto* stats = StatisticsData::GetSingleton();
    stats->GetStatistics(&a)->SetCustomFlt("number",1.25f);
    stats->GetStatistics(&a)->SetCustomStr("text","hello");
    stats->AddEncounter(&a,&b,ActorEncounter::EncounterType::Dominant);
    stats->AddEncounter(&b,&a,ActorEncounter::EncounterType::Submissive);
    const auto encounter = stats->GetEncounter(&a,&b);
    assert(encounter && encounter->GetTimesDominant(1)==2 && encounter->GetTimesSubmissive(2)==2);
    assert(encounter->GetParticipants().first.race.value==Registry::RaceKey::Human);
    SKSE::SerializationInterface io; stats->Save(&io);
    stats->Revert(nullptr); assert(!stats->GetEncounter(&a,&b));
    stats->Load(&io,2,static_cast<uint32_t>(io.bytes.size()));
    assert(stats->GetStatistics(&a)->GetCustomFlt("number")==1.25f);
    assert(stats->GetStatistics(&a)->GetCustomStr("text")==std::string("hello"));
    assert(stats->GetEncounter(&a,&b)->GetTimesMet()==2);
    stats->DeleteStatistics(1); // Returned encounter snapshot is still valid.
    assert(encounter->GetTimesMet()==2);
    // Concurrent increments are compound operations under the owning lock.
    std::vector<std::thread> workers;
    for(int n=0;n<4;++n)workers.emplace_back([&]{for(int i=0;i<1000;++i)stats->GetStatistics(&a)->AddStatistic(ActorStats::TimesTotal,1);});
    for(auto& worker:workers)worker.join();
    assert(stats->GetStatistics(&a)->GetStatistic(ActorStats::TimesTotal)==4000);
    RE::TESResetEvent reset{&a}; stats->ProcessEvent(&reset,nullptr);
    assert(stats->GetStatistics(&a)->GetStatistic(ActorStats::TimesTotal)==0);
    stats->Revert(nullptr);
    stats->AddEncounter(&a,&missing,ActorEncounter::EncounterType::Any);
    stats->AddEncounter(&b,&a,ActorEncounter::EncounterType::Any);
    stats->AddEncounter(&b,&c,ActorEncounter::EncounterType::Any);
    stats->AddEncounter(&a,&missing,ActorEncounter::EncounterType::Any);
    assert(stats->GetMostRecentEncounter(&b,ActorEncounter::EncounterType::Any)==&c);
    stats->Revert(nullptr);
    for(int i=0;i<300;++i) stats->AddEncounter(&a,&b,ActorEncounter::EncounterType::Aggressor);
    assert(stats->GetEncounter(&a,&b)->GetTimesMet()==255);
    assert(stats->GetEncounter(&a,&b)->GetTimesDominant(1)==255);
    assert(stats->GetEncounter(&a,&b)->GetTimesAssailant(1)==255);
    assert(stats->GetMostRecentEncounter(&a,ActorEncounter::EncounterType::Dominant)==&b);
    SKSE::SerializationInterface saturated;
    stats->Save(&saturated); stats->Revert(nullptr);
    stats->Load(&saturated,2,static_cast<uint32_t>(saturated.bytes.size()));
    assert(stats->GetEncounter(&a,&b)->GetTimesMet()==255);
    // Legacy v1 fixture: unresolved first actor, then string and raw MSVC variant.
    SKSE::SerializationInterface old;
    Util::WriteRecord(&old,uint64_t{2});
    for(uint32_t id : {99u,2u}) {
        Util::WriteRecord(&old,id);
        for(int i=0;i<ActorStats::Total;++i)Util::WriteRecord(&old,float(i));
        Util::WriteRecord(&old,uint64_t{2});
        Util::WriteRecordString(&old,std::string("text"));Util::WriteRecord(&old,uint32_t{1});Util::WriteRecordString(&old,std::string("legacy"));
        Util::WriteRecordString(&old,std::string("number"));Util::WriteRecord(&old,uint32_t{0});
        std::array<uint8_t,16> raw{};float number=3.5f;std::memcpy(raw.data(),&number,4);old.WriteRecordData(raw.data(),16);
    }
    stats->Load(&old,1,static_cast<uint32_t>(old.bytes.size()));
    const auto actors=stats->GetTrackedActors();assert(actors.size()==1 && actors[0]==&b);
    assert(stats->GetStatistics(&b)->GetCustomFlt("number")==3.5f);
    assert(stats->GetStatistics(&b)->GetCustomStr("text")==std::string("legacy"));
    assert(!stats->GetEncounter(&a,&missing));
    // Truncation fails atomically, with no huge allocation or partially loaded state.
    old.bytes.pop_back();old.pos=0;
    stats->Load(&old,1,static_cast<uint32_t>(old.bytes.size()));assert(stats->GetTrackedActors().empty());
    std::cout << "PASS: production statistics serialization/migration, missing IDs, encounters, locks and reset\n";
}
'''
    run('statistics', code)


if __name__ == '__main__':
    graph_test()
    statistics_test()
