#include "sslAnimationSlots.h"

#include "Registry/Library.h"
#include <unordered_map>

namespace Papyrus::AnimationSlots
{
    inline std::vector<RE::BSFixedString> ScenesToString(const std::vector<const Registry::Scene*>& a_scenes)
    {
        std::vector<RE::BSFixedString> ret{};
        ret.reserve(a_scenes.size());
        for (auto&& scene : a_scenes) {
            ret.push_back(scene->id);
        }
        return ret;
    }

    std::vector<RE::BSFixedString> GetByTagsImpl(VM* a_vm, StackID a_stackID, RE::TESQuest* a_qst, int32_t a_actorcount, std::vector<std::string_view> a_tags)
    {
        if (!a_qst) {
            a_vm->TraceStack("Cannot call GetByTagsImpl on a none object", a_stackID);
            return {};
        }
        if (a_actorcount <= 0 || a_actorcount > Registry::ActorFragment::MAX_ACTOR_COUNT) {
            const auto err = std::format("Actorcount should be between 1 and {} but was {}", Registry::ActorFragment::MAX_ACTOR_COUNT, a_actorcount);
            a_vm->TraceStack(err.c_str(), a_stackID);
            return {};
        }
        const auto lib = Registry::Library::GetSingleton();
        const auto scenes = lib->GetByTags(a_actorcount, a_tags);
        return ScenesToString(scenes);
    }

    std::vector<RE::BSFixedString> GetByTypeImpl(VM* a_vm, StackID a_stackID, RE::TESQuest* a_qst,
        int32_t a_actorcount, int32_t a_males, int32_t a_females, std::vector<std::string_view> a_tags)
    {
        if (!a_qst) {
            a_vm->TraceStack("Cannot call GetByTypeImpl on a none object", a_stackID);
            return {};
        }
        if (a_actorcount <= 0 || a_actorcount > Registry::ActorFragment::MAX_ACTOR_COUNT) {
            const auto err = std::format("Actorcount should be between 1 and {} but was {}", Registry::ActorFragment::MAX_ACTOR_COUNT, a_actorcount);
            a_vm->TraceStack(err.c_str(), a_stackID);
            return {};
        }
        const auto lib = Registry::Library::GetSingleton();
        auto scenes = lib->GetByTags(a_actorcount, a_tags);
        const auto size = scenes.size();
        const auto end = std::remove_if(scenes.begin(), scenes.end(), [&](const Registry::Scene* a_scene) {
            return !a_scene->Legacy_IsCompatibleSexCount(a_males, a_females);
        });
        scenes.erase(end, scenes.end());
        logger::info("Get by type found {} scenes; {}/{} match sex arguments", size, scenes.size(), size);
        return ScenesToString(scenes);
    }

    std::vector<RE::BSFixedString> PickByActorsImpl(VM* a_vm, StackID a_stackID, RE::TESQuest* a_qst, std::vector<RE::Actor*> a_positions, std::vector<std::string_view> a_tags)
    {
        if (!a_qst) {
            a_vm->TraceStack("Cannot call PickByActorsImpl on a none object", a_stackID);
            return {};
        }
        if (a_positions.empty() || std::find(a_positions.begin(), a_positions.end(), nullptr) != a_positions.end()) {
            a_vm->TraceStack("Cannot find scenes for a none position", a_stackID);
            return {};
        }
        const auto lib = Registry::Library::GetSingleton();
        std::vector<RE::Actor*> vic{};
        if (std::find(a_tags.begin(), a_tags.end(), "Forced") != a_tags.end()) {
            vic.push_back(a_positions[0]);
        }
        const auto scenes = lib->LookupScenes(a_positions, a_tags, vic);
        return ScenesToString(scenes);
    }

    std::vector<int32_t> FindProxyIndices(RE::StaticFunctionTag*, std::vector<RE::BSFixedString> a_proxies, std::vector<RE::BSFixedString> a_scenes, int32_t a_limit)
    {
        std::vector<int32_t> result;
        if (a_limit <= 0 || a_scenes.empty() || a_proxies.empty())
            return result;
        // BSFixedString equality uses the interned identity and treats all empty strings equally.
        const auto identity = [](const RE::BSFixedString& id) { return id.empty() ? nullptr : id.data(); };
        std::unordered_map<const char*, int32_t> byID;
        byID.reserve(a_proxies.size());
        for (size_t i = 0; i < a_proxies.size(); ++i)
            byID.try_emplace(identity(a_proxies[i]), static_cast<int32_t>(i));
        const auto limit = static_cast<size_t>(a_limit);
        result.reserve(std::min(limit, a_scenes.size()));
        for (const auto& scene : a_scenes) {
            if (const auto where = byID.find(identity(scene)); where != byID.end()) {
                result.push_back(where->second);
                if (result.size() == limit)
                    break;
            }
        }
        return result;
    }

    std::vector<RE::BSFixedString> GetAllPackages(RE::StaticFunctionTag*)
    {
        std::vector<RE::BSFixedString> ret{};
        Registry::Library::GetSingleton()->ForEachPackage([&](const Registry::AnimPackage* a_package) {
            ret.push_back(a_package->GetName());
            return false;
        });
        return ret;
    }

    std::vector<RE::BSFixedString> CreateProxyArray(RE::StaticFunctionTag*, uint32_t a_returnsize, uint32_t crt_specifier, RE::BSFixedString a_tags, RE::BSFixedString a_package)
    {
        std::vector<const Registry::Scene*> ret{};
        if (a_returnsize > 0)
            ret.reserve(a_returnsize);
        auto tags = Registry::TagDetails{ a_tags };
        const auto lib = Registry::Library::GetSingleton();
        RE::BSFixedString hash = "";
        lib->ForEachPackage([&](const Registry::AnimPackage* package) {
            if (package->GetName() == a_package) {
                hash = package->GetHash();
                return true;
            }
            return false;
        });
        lib->ForEachScene([&](const Registry::Scene* a_scene) {
            if (crt_specifier == 0 && a_scene->HasCreatures())
                return false;
            if (crt_specifier == 1 && !a_scene->HasCreatures())
                return false;
            if (!hash.empty() && a_scene->GetPackageHash() != hash)
                return false;
            if (!a_scene->IsCompatibleTags(tags))
                return false;
            ret.push_back(a_scene);
            return a_returnsize > 0 && ret.size() == a_returnsize;
        });
        std::sort(ret.begin(), ret.end(), [](const Registry::Scene*& a, const auto& b) {
            return a->name < b->name;
        });
        std::vector<RE::BSFixedString> ids{};
        ids.reserve(ret.size());
        std::ranges::transform(ret, std::back_inserter(ids), [](const auto& it) { return it->id; });
        return ids;
    }

}  // namespace Papyrus::AnimationSlots
