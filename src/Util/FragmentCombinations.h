#pragma once
#include <algorithm>
#include <set>
#include <vector>
namespace Util
{
    template <class T>
    std::set<std::vector<T>> UniqueFragmentCombinations(const std::vector<std::vector<T>>& choices)
    {
        std::set<std::vector<T>> partial{ std::vector<T>{} };
        for (const auto& alternatives : choices) {
            std::set<std::vector<T>> next;
            for (const auto& prefix : partial) {
                for (const auto& value : alternatives) {
                    auto key = prefix;
                    key.insert(std::lower_bound(key.begin(), key.end(), value), value);
                    next.insert(std::move(key));
                }
            }
            partial = std::move(next);
        }
        return partial;
    }
}
