#include "StripData.h"
#include "Util/SaveQueue.h"

namespace UserData
{
    void StripData::Load()
    {
        std::scoped_lock lock{ _m };
        try {
            const auto handler = RE::TESDataHandler::GetSingleton();
            auto root = YAML::LoadFile(STRIP_PATH);
            decltype(strips) loaded;
            for (const auto& mod : root) {
                const auto esp = mod.first.as<std::string>();
                if (handler->LookupModByName(esp) == nullptr) {
                    logger::info("Cannot load strip settings for {}. Plugin is not found", esp);
                    continue;
                }
                for (const auto& i : mod.second) {
                    const auto id = i.first.as<uint32_t>();
                    const auto formid = handler->LookupFormID(id, esp);
                    if (formid)
                        loaded[formid] = Strip(i.second.as<int32_t>());
                }
            }
            _root = std::move(root);
            strips = std::move(loaded);
        } catch (const std::exception& e) {
            logger::error("Unable to load data. Error: {}", e.what());
        }
        logger::info("Loaded {} custom strip settings", strips.size());
    }

    void StripData::Save()
    {
        std::scoped_lock lock{ _m };
        try {
            YAML::Node snapshot(YAML::NodeType::Map);
            const auto handler = RE::TESDataHandler::GetSingleton();
            // Preserve unavailable plugins; rebuild loaded plugins from live state,
            // including deletions and a complete reset.
            for (const auto& mod : _root) {
                const auto name = mod.first.as<std::string>();
                if (!handler->LookupModByName(name))
                    snapshot[name] = YAML::Clone(mod.second);
            }
            for (auto&& [formid, strip] : strips) {
                const auto entry = [&]() -> std::pair<std::string, uint32_t> {
                    const auto modidx = formid >> 24;
                    if (modidx == 0xFE) {
                        const auto file = RE::TESDataHandler::GetSingleton()->LookupLoadedLightModByIndex(static_cast<uint16_t>((formid >> 12) & 0xFFF));
                        return { file ? file->fileName : ""s, (0xFFF & formid) };
                    } else {
                        const auto file = RE::TESDataHandler::GetSingleton()->LookupLoadedModByIndex(static_cast<uint8_t>(modidx));
                        return { file ? file->fileName : ""s, (0xFFFFFF & formid) };
                    }
                }();
                if (entry.first.empty()) {
                    logger::error("Unable to find mod for formid {}", formid);
                    continue;
                }
                snapshot[entry.first][entry.second] = static_cast<int32_t>(strip);
            }
            Util::SaveQueue::Get().Submit(STRIP_PATH, YAML::Dump(snapshot));
            _root = std::move(snapshot);
        } catch (const std::exception& e) {
            logger::error("Unable to save StripConfig. Error: {}", e.what());
        }
        logger::info("Queued custom strip settings for {} mods", _root.size());
    }

    Strip StripData::CheckStrip(RE::TESForm* a_form)
    {
        std::scoped_lock lock{ _m };
        const auto it = strips.find(a_form->formID);
        if (it == strips.end() || it->second == Strip::None) {
            return CheckKeywords(a_form);
        }
        return it->second;
    }

    Strip StripData::CheckKeywords(RE::TESForm* a_form)
    {
        const auto& kwd = a_form->As<RE::BGSKeywordForm>();
        if (kwd) {
            if (kwd->ContainsKeywordString("NoStrip"))
                return Strip::NoStrip;
            if (kwd->ContainsKeywordString("AlwaysStrip"))
                return Strip::Always;
        }
        return Strip::None;
    }
}  // namespace UserData
