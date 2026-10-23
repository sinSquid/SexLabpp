#pragma once
#include <cstddef>
#include <cstdint>
#include <limits>
#include <vector>

namespace Util
{
    // Assign one distinct candidate to each slot. The first requiredCount
    // candidates must all appear; later candidates are optional, in priority order.
    inline std::vector<size_t> MatchRequiredSlots(size_t slotCount,
        const std::vector<uint32_t>& compatibleSlots, size_t requiredCount)
    {
        if (!slotCount || slotCount > 32 || requiredCount > slotCount || requiredCount > compatibleSlots.size())
            return {};
        constexpr auto empty = (std::numeric_limits<size_t>::max)();
        std::vector<size_t> assigned(slotCount, empty);
        const auto place = [&](auto&& self, size_t candidate, uint32_t& visited) -> bool {
            for (size_t slot = 0; slot < slotCount; ++slot) {
                const auto bit = uint32_t{1} << slot;
                if (!(compatibleSlots[candidate] & bit) || (visited & bit))
                    continue;
                visited |= bit;
                if (assigned[slot] == empty || self(self, assigned[slot], visited)) {
                    assigned[slot] = candidate;
                    return true;
                }
            }
            return false;
        };
        size_t matched = 0;
        for (size_t candidate = 0; candidate < compatibleSlots.size() && matched < slotCount; ++candidate) {
            uint32_t visited = 0;
            if (place(place, candidate, visited)) ++matched;
            else if (candidate < requiredCount) return {};
        }
        return matched == slotCount ? assigned : std::vector<size_t>{};
    }
}
