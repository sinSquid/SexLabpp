#pragma once

#include <array>
#include <bit>
#include <cstddef>

namespace Util
{
    template <size_t MaxCount>
    bool HasPerfectAssignment(const std::array<size_t, MaxCount>& a_compatible, size_t a_count)
    {
        if (a_count > MaxCount)
            return false;
        std::array<bool, size_t{ 1 } << MaxCount> reachable{};
        reachable[0] = true;
        const auto full = (size_t{ 1 } << a_count) - 1;
        for (size_t mask = 0; mask < full; ++mask) {
            if (!reachable[mask])
                continue;
            const auto actor = static_cast<size_t>(std::popcount(mask));
            auto available = a_compatible[actor] & full & ~mask;
            while (available != 0) {
                const auto bit = available & (~available + 1);
                reachable[mask | bit] = true;
                available &= available - 1;
            }
        }
        return reachable[full];
    }
}
