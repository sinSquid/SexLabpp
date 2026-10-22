from statistics_roundtrip import ROOT, function, run

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


if __name__ == '__main__':
    graph_test()
