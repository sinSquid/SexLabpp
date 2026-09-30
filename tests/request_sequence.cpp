#include "../src/Util/RequestSequence.h"
#include <algorithm>
#include <array>
#include <iostream>

int main()
{
    size_t cases = 0;
    std::array<int32_t, 4> order{ 1, 2, 3, 4 };
    do {
        Util::RequestSequence sequence;
        if (sequence.IsCurrent(0) || sequence.IsCurrent(-1) || sequence.IsCurrent(1))
            return 1;
        for (int32_t i = 1; i <= 4; ++i)
            if (sequence.Next() != i)
                return 1;
        int32_t committed = 0;
        for (const auto callback : order) {
            if (sequence.IsCurrent(callback))
                committed = callback;
        }
        if (committed != 4)
            return 1;
        ++cases;
    } while (std::next_permutation(order.begin(), order.end()));
    Util::RequestSequence interleaved;
    const auto first = interleaved.Next();
    if (!interleaved.IsCurrent(first))
        return 1;
    const auto second = interleaved.Next();
    if (interleaved.IsCurrent(first) || !interleaved.IsCurrent(second))
        return 1;
    std::cout << "PASS: " << cases << " callback permutations and interleaved issuance\n";
}
