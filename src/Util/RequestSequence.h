#pragma once

#include <cstdint>
#include <limits>

namespace Util
{
    // Owned by the game thread. Zero denotes the legacy, unsequenced API.
    class RequestSequence
    {
      public:
        int32_t Next()
        {
            current = current == std::numeric_limits<int32_t>::max() ? 1 : current + 1;
            return current;
        }
        bool IsCurrent(int32_t value) const { return value > 0 && value == current; }

      private:
        int32_t current{ 0 };
    };
}
