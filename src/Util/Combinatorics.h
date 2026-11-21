#pragma once

namespace Combinatorics
{
    enum class CResult
    {
        Next,
        Stop,
    };

    template <typename I>
    void ForEachCombination(const std::vector<std::vector<I>>& a_iterative, std::function<CResult(const std::vector<typename std::vector<I>::const_iterator>&)> a_iterator)
    {
        std::vector<typename std::vector<I>::const_iterator> it;
        if (a_iterative.empty())
            return;
        it.reserve(a_iterative.size());
        for (const auto& subvec : a_iterative) {
            if (subvec.empty())
                return;
            it.push_back(subvec.begin());
        }

        assert(it.size() == a_iterative.size());
        const auto K = it.size() - 1;
        while (it[0] != a_iterative[0].end()) {
            if (a_iterator(it) == CResult::Stop)
                return;
            // Next
            ++it[K];
            for (auto i = K; i > 0 && it[i] == a_iterative[i].end(); i--) {
                it[i] = a_iterative[i].begin();
                ++it[i - 1];
            }
        }
    }

}  // namespace Combinatorics
