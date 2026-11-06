#include "StripData.h"

namespace UserData
{
    void StripData::RemoveArmor(RE::TESForm* a_form)
    {
        strips.erase(a_form->formID);
        const auto file = a_form->GetFile(0);
        if (!file || !_root.IsMap())
            return;
        for (const auto& mod : _root) {
            const auto name = mod.first.as<std::string>("");
            if (_stricmp(name.c_str(), file->fileName) != 0 || !mod.second.IsMap())
                continue;
            auto entries = mod.second;
            // Match numeric IDs even when the existing YAML key uses hex notation.
            std::vector<YAML::Node> keys;
            for (const auto& entry : entries) {
                if (entry.first.as<uint32_t>(0xFFFFFFFF) == a_form->GetLocalFormID())
                    keys.push_back(entry.first);
            }
            for (const auto& key : keys)
                entries.remove(key);
        }
    }

    void StripData::RemoveArmorAll()
    {
        strips.clear();
        // Preserve overrides for temporarily missing plugins.
        if (!_root.IsMap())
            return;
        const auto handler = RE::TESDataHandler::GetSingleton();
        std::vector<std::string> loadedPlugins;
        for (const auto& mod : _root) {
            const auto name = mod.first.as<std::string>("");
            if (const auto file = handler->LookupModByName(name); file && file->compileIndex != 0xFF)
                loadedPlugins.push_back(name);
        }
        for (const auto& name : loadedPlugins)
            _root.remove(name);
    }

    void StripData::Load()
    {
        try {
            const auto handler = RE::TESDataHandler::GetSingleton();
            _root = YAML::LoadFile(STRIP_PATH);
            for (const auto&& mod : _root) {
                const auto esp = mod.first.as<std::string>();
                if (handler->LookupModByName(esp) == nullptr) {
                    logger::info("Cannot load strip settings for {}. Plugin is not found", esp);
                    continue;
                }
                for (const auto&& i : mod.second) {
                    const auto id = i.first.as<uint32_t>();
                    const auto formid = handler->LookupFormID(id, esp);
                    strips[formid] = Strip(i.second.as<int32_t>());
                }
            }
        } catch (const std::exception& e) {
            logger::error("Unable to load data. Error: {}", e.what());
        }
        logger::info("Loaded {} custom strip settings", strips.size());
    }

    void StripData::Save()
    {
        try {
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
                _root[entry.first][entry.second] = static_cast<int32_t>(strip);
            }
            std::ofstream{ STRIP_PATH } << _root;
        } catch (const std::exception& e) {
            logger::error("Unable to save StripConfig. Error: {}", e.what());
        }
        logger::info("Saved custom strip settings for {} mods", _root.size());
    }

    Strip StripData::CheckStrip(RE::TESForm* a_form)
    {
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
