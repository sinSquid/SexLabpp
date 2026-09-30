#include "../src/Util/Assignment.h"

#include <algorithm>
#include <iostream>
#include <numeric>
#include <random>

namespace
{
    bool ExhaustiveAssignment(const std::array<size_t, 5>& graph, size_t count)
    {
        std::array<size_t, 5> permutation{};
        std::iota(permutation.begin(), permutation.end(), size_t{ 0 });
        do {
            bool valid = true;
            for (size_t actor = 0; actor < count; ++actor)
                valid &= (graph[actor] & (size_t{ 1 } << permutation[actor])) != 0;
            if (valid)
                return true;
        } while (std::next_permutation(permutation.begin(), permutation.begin() + count));
        return false;
    }
}

int main()
{
    size_t tested = 0;
    const auto check = [&](const std::array<size_t, 5>& graph, size_t count) {
        ++tested;
        return Util::HasPerfectAssignment(graph, count) == ExhaustiveAssignment(graph, count);
    };
    // Every bipartite graph for up to four actors, including Hall-condition failures.
    for (size_t count = 0; count <= 4; ++count) {
        const auto rowMask = (size_t{ 1 } << count) - 1;
        for (size_t matrix = 0; matrix < (size_t{ 1 } << (count * count)); ++matrix) {
            std::array<size_t, 5> graph{};
            for (size_t actor = 0; actor < count; ++actor)
                graph[actor] = (matrix >> (actor * count)) & rowMask;
            if (!check(graph, count)) {
                std::cerr << "Assignment mismatch: count=" << count << " matrix=" << matrix << '\n';
                return 1;
            }
        }
    }
    std::mt19937 random{ 0x534c5050 };
    for (size_t sample = 0; sample < 50000; ++sample) {
        std::array<size_t, 5> graph{};
        for (auto& row : graph)
            row = random() & 31u;
        if (!check(graph, 5)) {
            std::cerr << "Five-actor assignment mismatch\n";
            return 1;
        }
    }
    const std::array<size_t, 5> empty{};
    if (Util::HasPerfectAssignment(empty, 6))
        return 1;
    // Out-of-range compatibility bits must never create fictitious positions.
    for (size_t count = 0; count <= 5; ++count) {
        std::array<size_t, 5> graph{};
        graph.fill(~((size_t{ 1 } << count) - 1));
        if (!check(graph, count))
            return 1;
        for (size_t i = 0; i < count; ++i)
            graph[i] |= size_t{ 1 } << i;
        if (!check(graph, count))
            return 1;
    }
    std::cout << "PASS: " << tested << " assignment graphs match exhaustive enumeration\n";
}
