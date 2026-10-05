#include "Voice.h"

#include "Util/SaveQueue.h"
#include "Util/StringUtil.h"

namespace Registry
{
    Voice::Voice(const YAML::Node& a_node) :
      name(a_node["Name"].as<std::string>()),
      displayName(a_node["DisplayName"].as<std::string>(""s)),
      enabled(true),
      sex([&]() {
          auto node = a_node["Actor"]["Sex"];
          if (!node.IsDefined())
              return RE::SEXES::kNone;
          auto str = node.as<std::string>();
          Util::ToLower(str);
          return str == "female" ? RE::SEXES::kFemale :
                 str == "male"   ? RE::SEXES::kMale :
                                   RE::SEXES::kNone;
      }()),
      races([&]() -> decltype(races) {
          const auto& node = a_node["Actor"]["Race"];
          if (node.IsScalar())
              return { RaceKey{ node.as<std::string>() } };
          decltype(races) result;
          for (const auto& race : node)
              result.emplace_back(race.as<std::string>());
          return result;
      }()),
      pitch([&]() {
          const auto& node = a_node["Actor"]["Pitch"];
          if (!node.IsDefined())
              return Pitch::Unknown;
          return magic_enum::enum_cast<Pitch>(node.as<std::string>(), magic_enum::case_insensitive).value_or(Pitch::Unknown);
      }()),
      tags([&]() -> decltype(tags) {
          const auto& node = a_node["Tags"];
          if (!node.IsDefined())
              return {};
          return { node.IsScalar() ? std::vector{ node.as<std::string>() } : node.as<std::vector<std::string>>() };
      }()),
      defaultset(a_node),
      extrasets([&]() {
          decltype(extrasets) ret{};
          ret.emplace_back(a_node);
          auto extra = a_node["Extra"];
          if (extra.IsDefined())
              for (auto&& it : extra) {
                  ret.emplace_back(it);
              }
          return ret;
      }())
    {}

    const VoiceSet& Voice::GetApplicableSet(REX::EnumSet<VoiceAnnotation> a_annotation) const
    {
        const auto requested = a_annotation.underlying();
        // Try every nonempty subset. Descending masks preserve the existing
        // preference for Muffled, but also allow role-only fallback.
        for (auto subset = requested; subset != 0; subset = (subset - 1) & requested) {
            for (const auto& vset : extrasets) {
                if (vset.IsValid(VoiceAnnotation(subset)))
                    return vset;
            }
        }
        return defaultset;
    }

    RE::TESSound* Voice::PickSound(LegacyVoice a_legacysetting) const
    {
        const auto& set = a_legacysetting == LegacyVoice::Medium ? GetApplicableSet(VoiceAnnotation::Submissive) : defaultset;
        return set.Get(a_legacysetting);
    }

    RE::TESSound* Voice::PickSound(uint32_t a_excitement, REX::EnumSet<VoiceAnnotation> a_annotation) const
    {
        return GetApplicableSet(a_annotation).Get(a_excitement);
    }

    RE::TESSound* Voice::PickOrgasmSound(REX::EnumSet<VoiceAnnotation> a_annotation) const
    {
        const auto& s = GetApplicableSet(a_annotation);
        return s.GetOrgasm() ? s.GetOrgasm() : s.Get(100);
    }

    void Voice::SaveToFile(std::string_view a_fileLocation) const
    {
        const std::string_view id{ GetId().data() };
        // IDs are metadata too, but must be a single file stem when exported.
        if (id.empty() || id == "." || id == ".." || id.find_first_of("/\\:") != std::string_view::npos)
            throw std::invalid_argument("Voice ID cannot be used as a file name");
        const auto path = fs::path{ a_fileLocation } / std::format("{}.yaml", id);
        if (fs::exists(path)) {
            return;
        }
        YAML::Node root{};
        root["Name"] = GetId().data();
        root["DisplayName"] = displayName.empty() ? "" : displayName.data();
        root["Actor"]["Pitch"] = std::string(magic_enum::enum_name(pitch));
        root["Tags"] = YAML::Node(YAML::NodeType::Sequence);
        switch (sex) {
        case RE::SEXES::kFemale:
            root["Actor"]["Sex"] = "Female";
            break;
        case RE::SEXES::kMale:
            root["Actor"]["Sex"] = "Male";
            break;
        default:
            root["Actor"]["Sex"] = "Any";
            break;
        }
        if (races.empty()) {
            root["Actor"]["Race"].push_back("Human");
        } else {
            for (auto&& r : races) {
                auto str = r.AsString();
                root["Actor"]["Race"].push_back(str.data());
            }
        }
        for (auto&& t : tags.AsVector()) {
            root["Tags"].push_back(t.data());
        }
        const auto dSet = defaultset.AsYaml();
        root["Voices"] = dSet["Voices"];
        if (dSet["Orgasm"].IsDefined()) {
            root["Orgasm"] = dSet["Orgasm"];
        }
        for (auto&& e : extrasets) {
            root["Extra"].push_back(e.AsYaml());
        }
        Util::AtomicWrite(path, YAML::Dump(root));
    }

    void Voice::Save(YAML::Node& a_node) const
    {
        a_node = enabled;
    }

    void Voice::Load(const YAML::Node& a_node)
    {
        if (a_node.IsDefined()) {
            enabled = a_node.as<bool>();
        }
    }


    VoiceSet::VoiceSet(const YAML::Node& a_node)
    {
        auto v = a_node["Voices"];
        if (v.IsMap()) {
            for (auto&& it : v) {
                auto sound = Util::FormFromString<RE::TESSound*>(it.first.as<std::string>());
                if (!sound)
                    continue;
                const auto priority = it.second.as<uint32_t>();
                if (priority > 255)
                    throw std::runtime_error("Voice priority exceeds uint8 range");
                data.emplace_back(sound, static_cast<uint8_t>(priority));
            }
        } else {
            const auto max = v.size();
            for (size_t i = 0; i < max; ++i) {
                auto sound = Util::FormFromString<RE::TESSound*>(v[i].as<std::string>());
                if (!sound)
                    continue;
                data.emplace_back(sound, static_cast<uint8_t>((static_cast<double>(i) / static_cast<double>(max)) * 100.0));
            }
        }
        if (data.empty()) {
            throw std::runtime_error("Need at least 1 valid Voice per Set");
        }
        std::sort(data.begin(), data.end(), [](auto& a, auto& b) {
            return a.second < b.second;
        });
        if (auto o = a_node["Orgasm"]; o.IsDefined()) {
            orgasm = Util::FormFromString<RE::TESSound*>(o.as<std::string>());
        }
        auto convec = a_node["Conditions"];
        if (!convec.IsDefined())
            return;
        for (auto&& con : convec) {
            auto key = con.first.as<std::string>();
            auto value = con.second.as<bool>();
            if (!value)
                continue;
            auto annotation = magic_enum::enum_cast<VoiceAnnotation>(key, magic_enum::case_insensitive);
            if (annotation.has_value()) {
                annotations |= annotation.value();
            }
        }
    }

    VoiceSet::VoiceSet(bool a_aslegacyextra) :
      data({ { nullptr, uint8_t(0) }, { nullptr, uint8_t(75) } })
    {
        if (a_aslegacyextra) {
            annotations |= VoiceAnnotation::Submissive;
        }
    }

    RE::TESSound* VoiceSet::Get(uint32_t a_priority) const
    {
        const auto next = std::upper_bound(data.begin(), data.end(), a_priority,
            [](uint32_t priority, const auto& entry) { return priority < entry.second; });
        return next == data.begin() ? nullptr : std::prev(next)->first;
    }

    RE::TESSound* VoiceSet::Get(LegacyVoice a_setting) const
    {
        switch (a_setting) {
        case LegacyVoice::Hot:
            return data.back().first;
        default:
            return data.front().first;
        }
    }

    void VoiceSet::SetSound(bool front, RE::TESSound* a_sound)
    {
        auto& obj = front ? data.front() : data.back();
        obj.first = a_sound;
    }

    YAML::Node VoiceSet::AsYaml() const
    {
        YAML::Node ret{};
        for (auto&& [v, prio] : data) {
            if (!v)
                continue;
            auto key = Util::FormToString(v);
            if (ret["Voices"][key].IsDefined())
                continue;
            ret["Voices"][key] = static_cast<int32_t>(prio);
        }
        if (orgasm) {
            ret["Orgasm"] = Util::FormToString(orgasm);
        }
        const auto components = FlagToComponents(annotations.get());
        for (auto&& c : components) {
            const auto name = magic_enum::enum_name(c);
            ret["Conditions"][name.data()] = true;
        }
        return ret;
    }

}  // namespace Registry
