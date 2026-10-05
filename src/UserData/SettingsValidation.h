#pragma once

#include <algorithm>
#include <cctype>
#include <cmath>
#include <string>
#include <string_view>
#include <type_traits>
#include <vector>

namespace SettingsValidation
{
    inline std::string Key(std::string_view key)
    {
        std::string result(key);
        for (auto& c : result)
            c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        return result;
    }

    // Float settings currently describe nonnegative dimensions, durations,
    // strengths and probabilities. Reject pathological magnitudes before casts
    // and products; keep ordinary manual customization outside MCM sliders.
    template <typename T>
    bool IsValid(std::string_view key, const T& value)
    {
        const auto name = Key(key);
        if constexpr (std::is_floating_point_v<T>) {
            if (!std::isfinite(value) || value < 0 || value > 1000000)
                return false;
            if (name == "fmenuscalemult" || name == "fmenutextscalemult")
                return value >= 0.1 && value <= 10;
            if (name == "fminscale" || name == "ftimers" || name == "fdistancemouth" || name == "fdistancecrotch" ||
                name == "fclosetoheadratio" || name == "fveryclosetoheadratio" || name == "fmintypeduration" ||
                name == "fminspeedpenetration" || name == "fmaxkissspeed")
                return value > 0;
            if (name == "fvoicevolume" || name == "fsfxvolume" || name == "fcumalpha" ||
                name == "fghostmodealpha" || name == "ffurniturepreference" ||
                name == "fenterthreshold" || name == "fexitthreshold" || name == "fenterthresholdsoftmax")
                return value <= 1;
        } else if constexpr (std::is_same_v<T, std::vector<float>>) {
            return std::ranges::all_of(value, [&](float item) { return IsValid(key, item); });
        } else if constexpr (std::is_integral_v<T> && !std::is_same_v<T, bool>) {
            if (name == "iaskbed") return value >= 0 && value <= 4;
            if (name == "inpcbed") return value >= 0 && value <= 2;
            if (name == "iclimaxtype") return value >= 0 && value <= 2;
            if (name == "ilovensestrength" || name == "ilovensestrengthorgasm") return value >= 0 && value <= 20;
        }
        return true;
    }
}
