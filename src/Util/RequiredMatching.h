#pragma once
#include <cstddef>
#include <functional>
#include <vector>
namespace Util
{
    inline std::vector<int> MatchRequired(const std::vector<std::vector<size_t>>& edges, size_t positions, size_t required)
    {
        if (required > positions || required > edges.size())
            return {};
        std::vector<int> occupants(positions, -1);
        size_t filled = 0;
        for (size_t actor = 0; actor < edges.size() && filled < positions; ++actor) {
            std::vector<bool> visited(positions, false);
            std::function<bool(size_t)> place = [&](size_t candidate) {
                for (const auto slot : edges[candidate]) {
                    if (slot >= positions || visited[slot])
                        continue;
                    visited[slot] = true;
                    if (occupants[slot] < 0 || place(static_cast<size_t>(occupants[slot]))) {
                        occupants[slot] = static_cast<int>(candidate);
                        return true;
                    }
                }
                return false;
            };
            if (place(actor))
                ++filled;
            else if (actor < required)
                return {};
        }
        return filled == positions ? occupants : std::vector<int>{};
    }
}
