#include "Library.h"

#include "Define/RaceKey.h"

namespace Registry
{
    std::vector<const Scene*> Library::LookupScenes(const std::vector<RE::Actor*>& a_actors, const std::vector<std::string_view>& a_tags, const std::vector<RE::Actor*>& a_submissives) const
    {
        const auto tStart = std::chrono::high_resolution_clock::now();
        std::vector<ActorFragment> fragments;
        fragments.reserve(a_actors.size());
        for (auto* actor : a_actors) {
            if (!actor) {
                logger::warn("Warning: NULL Actor passed to LookupScenes");
                continue;
            }
            fragments.emplace_back(actor, std::ranges::contains(a_submissives, actor));
        }
        if (fragments.empty() || fragments.size() > ActorFragment::MAX_ACTOR_COUNT) {
            logger::warn("Invalid query: {} valid actors passed to LookupScenes", fragments.size());
            return {};
        }
        const auto hash = ActorFragment::MakeFragmentHash(std::move(fragments));
        TagDetails tags{ a_tags };
        std::string tagstr{ "[" };
        bool firstTag = true;
        for (const auto tag : a_tags) {
            if (!firstTag)
                tagstr += ", ";
            tagstr.append(tag);
            firstTag = false;
        }
        tagstr += ']';

        const std::shared_lock lock{ _mScenes };
        const auto where = this->scenes.find(hash);
        if (where == this->scenes.end()) {
            logger::warn("Invalid query: [{} | {} | {}]; No animations for given actors", a_actors.size(), hash.to_string(), tagstr);
            return {};
        }
        const auto& rawScenes = where->second;

        std::vector<const Scene*> ret{};
        ret.reserve(rawScenes.size());
        size_t enabledCount = 0;
        for (const auto* scene : rawScenes) {
            if (!scene->IsEnabled() || scene->IsPrivate())
                continue;
            ++enabledCount;
            if (scene->IsCompatibleTags(tags))
                ret.push_back(scene);
        }
        if (enabledCount == 0) {
            logger::warn("Invalid query: [{} | {} | {}]; 0/{} animations are enabled", a_actors.size(), hash.to_string(), tagstr, where->second.size());
            return {};
        }
        if (ret.empty()) {
            logger::warn("Invalid query: [{} | {} | {}]; 0/{} animations use requested tags", a_actors.size(), hash.to_string(), tagstr, enabledCount);
            return {};
        }
        const auto tEnd = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> ms = tEnd - tStart;
        logger::debug("Found {} scenes for query [{} | {} | {}] actors in {}ms", ret.size(), a_actors.size(), hash.to_string(), tagstr, ms.count());
        return ret;
    }

    std::vector<const Scene*> Library::GetByTags(int32_t a_positions, const std::vector<std::string_view>& a_tags) const
    {
        if (a_positions <= 0 || a_positions > ActorFragment::MAX_ACTOR_COUNT)
            return {};
        TagDetails tags{ a_tags };
        const std::shared_lock lock{ _mScenes };
        std::vector<const Scene*> ret{};
        const auto& candidates = scenePositionIndex[static_cast<size_t>(a_positions)];
        ret.reserve(candidates.size());
        for (const auto* scene : candidates) {
            if (!scene->IsEnabled() || scene->IsPrivate())
                continue;
            if (scene->positions.size() != a_positions)
                continue;
            if (!scene->IsCompatibleTags(tags))
                continue;
            ret.push_back(scene);
        }
        return ret;
    }

    std::vector<RE::BSFixedString> Library::GetLegacyProxyIds(size_t a_limit, uint32_t a_creatureSpecifier) const
    {
        const auto key = std::pair{ a_limit, std::min(a_creatureSpecifier, 2u) };
        {
            std::shared_lock lock{ _mScenes };
            if (const auto where = legacyProxyCache.find(key); where != legacyProxyCache.end())
                return where->second;
        }
        std::unique_lock lock{ _mScenes };
        if (const auto where = legacyProxyCache.find(key); where != legacyProxyCache.end())
            return where->second;
        std::vector<const Scene*> selected;
        for (const auto& [id, scene] : sceneMap) {
            if ((key.second == 0 && scene->HasCreatures()) || (key.second == 1 && !scene->HasCreatures()))
                continue;
            selected.push_back(scene);
            if (a_limit > 0 && selected.size() == a_limit)
                break;
        }
        // Preserve the legacy selection limit and its original name ordering.
        std::sort(selected.begin(), selected.end(), [](const auto* lhs, const auto* rhs) {
            return lhs->name < rhs->name;
        });
        std::vector<RE::BSFixedString> ids;
        ids.reserve(selected.size());
        for (const auto* scene : selected)
            ids.emplace_back(scene->id);
        // Normal callers use only two alias limits. Bound storage for arbitrary external queries.
        if (legacyProxyCache.size() >= 32)
            legacyProxyCache.clear();
        legacyProxyCache.emplace(key, ids);
        return ids;
    }

    const AnimPackage* Library::GetPackageFromScene(const Scene* a_scene) const
    {
        std::shared_lock lock{ _mScenes };
        const auto where = scenePackageMap.find(a_scene);
        return where != scenePackageMap.end() ? where->second : nullptr;
    }

    const Scene* Library::GetSceneById(const RE::BSFixedString& a_id) const
    {
        std::shared_lock lock{ _mScenes };
        const auto where = sceneMap.find(a_id);
        return where != sceneMap.end() ? where->second : nullptr;
    }

    const Scene* Library::GetSceneByName(const RE::BSFixedString& a_name) const
    {
        std::shared_lock lock{ _mScenes };
        const auto where = sceneNameMap.find(a_name);
        return where != sceneNameMap.end() ? where->second : nullptr;
    }

    size_t Library::GetSceneCount() const
    {
        std::shared_lock lock{ _mScenes };
        return sceneMap.size();
    }

    bool Library::EditScene(const RE::BSFixedString& a_id, const std::function<void(Scene*)>& a_func)
    {
        auto scene = GetSceneById(a_id);
        if (!scene) {
            logger::error("Scene {} not found", a_id.c_str());
            return false;
        }
        EditScene(scene, a_func);
        return true;
    }

    void Library::EditScene(const Registry::Scene* a_scene, const std::function<void(Scene*)>& a_func)
    {
        std::unique_lock lock{ _mScenes };
        const auto scene = const_cast<Scene*>(a_scene);
        const auto oldCount = scene->positions.size();
        a_func(scene);
        legacyProxyCache.clear();
        if (oldCount != scene->positions.size()) {
            for (auto& bucket : scenePositionIndex)
                bucket.clear();
            for (const auto& [id, entry] : sceneMap) {
                if (!entry->positions.empty() && entry->positions.size() <= ActorFragment::MAX_ACTOR_COUNT)
                    scenePositionIndex[entry->positions.size()].push_back(entry);
            }
        }
    }

    bool Library::ForEachPackage(std::function<bool(const AnimPackage*)> a_visitor) const
    {
        std::shared_lock lock{ _mScenes };
        for (auto&& package : packages) {
            if (a_visitor(package.get()))
                return true;
        }
        return false;
    }

    bool Library::ForEachScene(std::function<bool(const Scene*)> a_visitor) const
    {
        std::shared_lock lock{ _mScenes };
        for (auto&& [key, scene] : sceneMap) {
            if (a_visitor(scene))
                return true;
        }
        return false;
    }

    std::vector<RE::BSFixedString> Library::GetAllVoiceIds(RaceKey a_race) const
    {
        std::shared_lock lock{ _mVoice };
        std::vector<RE::BSFixedString> result;
        result.reserve(voices.size());
        for (const auto& it : voices) {
            const auto& [name, voice] = it;
            if (a_race.Is(RaceKey::None) || voice.HasRace(a_race))
                result.push_back(name);
        }
        return result;
    }

    bool Library::ForEachVoice(std::function<bool(const Voice&)> a_visitor) const
    {
        std::shared_lock lock{ _mVoice };
        for (auto&& [name, voice] : voices) {
            if (a_visitor(voice))
                return true;
        }
        return false;
    }

    const Voice* Library::GetVoice(RE::Actor* a_actor, const TagDetails& a_tags)
    {
        if (!a_actor)
            return nullptr;
        const auto actorId = a_actor->GetFormID();
        {
            std::shared_lock lock{ _mVoice };
            if (const auto saved = savedVoices.find(actorId); saved != savedVoices.end() && saved->second)
                return saved->second;
        }
        std::unique_lock lock{ _mVoice };
        if (const auto saved = savedVoices.find(actorId); saved != savedVoices.end() && saved->second)
            return saved->second;
        const auto base = a_actor->GetActorBase();
        if (!base || !a_actor->GetRace()) {
            logger::error("GetVoice: Actor {} has no actor base or race", a_actor->GetFormID());
            return nullptr;
        }
        const RaceKey actRace{ a_actor };
        if (!actRace.IsValid()) {
            logger::error("GetVoice: Actor {} has invalid racekey", a_actor->GetFormID());
            return nullptr;
        }
        const auto sex = base->GetSex();
        std::vector<const Voice*> ret{};
        for (auto&& [name, voice] : voices) {
            if (!voice.enabled || voice.sex != RE::SEXES::kNone && voice.sex != sex)
                continue;
            if (!voice.HasRace(actRace) || !a_tags.MatchTags(voice.tags))
                continue;
            ret.push_back(&voice);
        }
        if (ret.empty())
            return nullptr;
        if (auto voiceForm = base->GetVoiceType()) {
            auto where = savedPitches.find(voiceForm->formID);
            if (where != savedPitches.end()) {
                const auto [pitch, voice] = where->second;
                if (voice != nullptr)
                    return voice;
                const auto w = std::remove_if(ret.begin(), ret.end(), [&](const auto& v) {
                    return v->pitch != Pitch::Unknown && v->pitch != pitch;
                });
                if (w != ret.begin() && w != ret.end()) {
                    ret.erase(w, ret.end());
                }
            }
        }
        return savedVoices[actorId] = Random::draw(ret);
    }

    const Voice* Library::GetVoice(const TagDetails& tags) const
    {
        std::shared_lock lock{ _mVoice };
        std::vector<const Voice*> ret{};
        for (const auto& [_, voice] : voices) {
            if (!voice.enabled || !tags.MatchTags(voice.tags))
                continue;
            ret.push_back(&voice);
        }
        return ret.empty() ? nullptr : Random::draw(ret);
    }

    const Voice* Library::GetVoice(RaceKey a_race) const
    {
        std::shared_lock lock{ _mVoice };
        std::vector<const Voice*> ret{};
        for (auto&& [_, voice] : voices) {
            if (!voice.enabled || !voice.HasRace(a_race))
                continue;
            ret.push_back(&voice);
        }
        return ret.empty() ? nullptr : Random::draw(ret);
    }

    const Voice* Library::GetVoiceById(RE::BSFixedString a_voice) const
    {
        std::shared_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        return v == voices.end() ? nullptr : &v->second;
    }

    bool Library::ReadVoice(RE::BSFixedString a_voice, const std::function<void(const Voice&)>& a_reader) const
    {
        std::shared_lock lock{ _mVoice };
        const auto voice = voices.find(a_voice);
        if (voice == voices.end())
            return false;
        a_reader(voice->second);
        return true;
    }

    bool Library::CreateVoice(RE::BSFixedString a_voice)
    {
        std::unique_lock lock{ _mVoice };
        if (voices.contains(a_voice)) {
            logger::error("Voice {} has already been initialized", a_voice);
            return false;
        }
        voices.emplace(a_voice, Voice{ a_voice });
        return true;
    }

    void Library::WriteVoiceToFile(RE::BSFixedString a_voice) const
    {
        std::optional<Voice> snapshot;
        if (!ReadVoice(a_voice, [&](const Voice& voice) { snapshot.emplace(voice); })) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        // Disk I/O uses a consistent copy without blocking voice queries or edits.
        snapshot->SaveToFile(VOICE_PATH);
    }

    std::vector<RE::Actor*> Library::GetSavedActors() const
    {
        std::shared_lock lock{ _mVoice };
        std::vector<RE::Actor*> result;
        result.reserve(savedVoices.size());
        for (const auto& it : savedVoices) {
            auto act = RE::TESForm::LookupByID<RE::Actor>(it.first);
            if (act)
                result.push_back(act);
        }
        return result;
    }

    const Voice* Library::GetSavedVoice(RE::FormID a_key) const
    {
        std::shared_lock lock{ _mVoice };
        auto w = savedVoices.find(a_key);
        return w == savedVoices.end() ? nullptr : w->second;
    }

    void Library::SaveVoice(RE::FormID a_key, RE::BSFixedString a_voice)
    {
        std::unique_lock lock{ _mVoice };
        const auto voice = voices.find(a_voice);
        if (voice != voices.end()) {
            savedVoices.insert_or_assign(a_key, &voice->second);
        } else {
            savedVoices.erase(a_key);
        }
    }

    void Library::ClearVoice(RE::FormID a_key)
    {
        std::unique_lock lock{ _mVoice };
        savedVoices.erase(a_key);
    }

    RE::TESSound* Library::PickSound(RE::BSFixedString a_voice, LegacyVoice a_legacysetting) const
    {
        std::shared_lock lock{ _mVoice };
        const auto voice = voices.find(a_voice);
        if (voice == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return nullptr;
        }
        return voice->second.PickSound(a_legacysetting);
    }

    RE::TESSound* Library::PickSound(RE::BSFixedString a_voice, uint32_t a_excitement, REX::EnumSet<VoiceAnnotation> a_annotation) const
    {
        std::shared_lock lock{ _mVoice };
        const auto voice = voices.find(a_voice);
        if (voice == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return nullptr;
        }
        return voice->second.PickSound(a_excitement, a_annotation);
    }

    RE::TESSound* Library::PickOrgasmSound(RE::BSFixedString a_voice, REX::EnumSet<VoiceAnnotation> a_annotation) const
    {
        std::shared_lock lock{ _mVoice };
        const auto voice = voices.find(a_voice);
        if (voice == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return nullptr;
        }
        return voice->second.PickOrgasmSound(a_annotation);
    }

    void Library::SetVoiceEnabled(RE::BSFixedString a_voice, bool a_enabled)
    {
        std::unique_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        if (v == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        v->second.enabled = a_enabled;
    }

    void Library::SetVoiceSound(RE::BSFixedString a_voice, LegacyVoice a_legacysetting, RE::TESSound* a_sound)
    {
        std::unique_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        if (v == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        auto& voice = v->second;
        switch (a_legacysetting) {
        case LegacyVoice::Mild:
            voice.defaultset.SetSound(true, a_sound);
            break;
        case LegacyVoice::Medium:
            if (voice.extrasets.empty()) {
                logger::error("Voice {} has no extrasets", a_voice);
                break;
            }
            voice.extrasets.front().SetSound(true, a_sound);
            break;
        case LegacyVoice::Hot:
            voice.defaultset.SetSound(false, a_sound);
            if (!voice.extrasets.empty())
                voice.extrasets.front().SetSound(false, a_sound);
            break;
        }
    }

    void Library::SetVoiceTags(RE::BSFixedString a_voice, const std::vector<RE::BSFixedString>& a_tags)
    {
        std::unique_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        if (v == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        v->second.tags.AddTag(a_tags);
    }

    void Library::SetVoiceRace(RE::BSFixedString a_voice, const std::vector<RaceKey>& a_races)
    {
        std::unique_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        if (v == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        auto& voice = v->second;
        if (!a_races.empty() && !std::ranges::contains(a_races, RaceKey::Human, [](auto& it) { return it.value; })) {
            voice.tags.AddTag("Creature");
        } else {
            voice.tags.RemoveTag("Creature");
        }
        voice.races = a_races;
    }

    void Library::SetVoiceSex(RE::BSFixedString a_voice, RE::SEXES::SEX a_sex)
    {
        std::unique_lock lock{ _mVoice };
        auto v = voices.find(a_voice);
        if (v == voices.end()) {
            logger::error("Voice {} not found", a_voice);
            return;
        }
        auto& voice = v->second;
        switch (a_sex) {
        case RE::SEXES::kFemale:
            voice.tags.RemoveTag("Male");
            voice.tags.AddTag("Female");
            break;
        case RE::SEXES::kMale:
            voice.tags.AddTag("Male");
            voice.tags.RemoveTag("Female");
            break;
        default:
            voice.tags.AddTag("Female");
            voice.tags.AddTag("Male");
            break;
        }
        voice.sex = a_sex;
    }

    const Expression* Library::GetExpressionById(const RE::BSFixedString& a_id) const
    {
        std::shared_lock lock{ _mExpressions };
        auto where = expressions.find(a_id);
        return where == expressions.end() ? nullptr : &where->second;
    }

    bool Library::ReadExpression(const RE::BSFixedString& a_id, const std::function<void(const Expression&)>& a_reader) const
    {
        std::shared_lock lock{ _mExpressions };
        const auto where = expressions.find(a_id);
        if (where == expressions.end())
            return false;
        a_reader(where->second);
        return true;
    }

    const Expression* Library::GetExpression(const TagDetails& a_details) const
    {
        std::shared_lock lock{ _mExpressions };
        std::vector<const Expression*> ret{};
        for (auto&& [id, expression] : expressions) {
            if (expression.IsEnabled() && a_details.MatchTags(expression.GetTags())) {
                ret.push_back(&expression);
            }
        }
        return ret.empty() ? nullptr : Random::draw(ret);
    }

    bool Library::ForEachExpression(std::function<bool(const Expression&)> a_func) const
    {
        std::shared_lock lock{ _mExpressions };
        for (auto&& [id, expression] : expressions) {
            if (a_func(expression)) {
                return true;
            }
        }
        return false;
    }

    bool Library::CreateExpression(const RE::BSFixedString& a_id)
    {
        std::unique_lock lock{ _mExpressions };
        if (expressions.contains(a_id)) {
            logger::error("Expression {} has already been initialized", a_id);
            return false;
        }
        expressions.emplace(a_id, Expression{ a_id });
        return true;
    }

    bool Library::MarkExpressionForSave(const RE::BSFixedString& a_id)
    {
        std::unique_lock lock{ _mExpressions };
        const auto where = expressions.find(a_id);
        if (where == expressions.end())
            return false;
        where->second.has_edits = true;
        return true;
    }

    void Library::UpdateExpressionValues(RE::BSFixedString a_id, bool a_female, int a_level, const std::vector<float>& a_values)
    {
        std::unique_lock lock{ _mExpressions };
        auto w = expressions.find(a_id);
        if (w == expressions.end()) {
            logger::error("Expression {} not found", a_id);
            return;
        }
        w->second.UpdateValues(a_female, a_level, a_values);
    }

    void Library::UpdateExpressionTags(RE::BSFixedString a_id, const TagData& a_newtags)
    {
        std::unique_lock lock{ _mExpressions };
        auto w = expressions.find(a_id);
        if (w == expressions.end()) {
            logger::error("Expression {} not found", a_id);
            return;
        }
        w->second.UpdateTags(a_newtags);
    }

    void Library::SetExpressionScaling(RE::BSFixedString a_id, Expression::Scaling a_scaling)
    {
        std::unique_lock lock{ _mExpressions };
        auto w = expressions.find(a_id);
        if (w == expressions.end()) {
            logger::error("Expression {} not found", a_id);
            return;
        }
        w->second.SetScaling(a_scaling);
    }

    void Library::SetExpressionEnabled(RE::BSFixedString a_id, bool a_enabled)
    {
        std::unique_lock lock{ _mExpressions };
        auto w = expressions.find(a_id);
        if (w == expressions.end()) {
            logger::error("Expression {} not found", a_id);
            return;
        }
        w->second.SetEnabled(a_enabled);
    }


    RE::BSFixedString Library::PickRandomFxSet(FxType a_type) const
    {
        const auto typeIdx = static_cast<size_t>(a_type);
        if (fxList[typeIdx].empty()) {
            return "";
        }
        const auto i = Random::draw<size_t>(0, fxList[typeIdx].size() - 1);
        return fxList[typeIdx][i].first;
    }

    uint8_t Library::GetFxCount(FxType a_type, RE::BSFixedString a_set) const
    {
        const auto typeIdx = static_cast<size_t>(a_type);
        const auto it = std::find_if(fxList[typeIdx].begin(), fxList[typeIdx].end(), [&](const auto& pair) {
            return pair.first == a_set;
        });
        if (it != fxList[typeIdx].end()) {
            return it->second;
        }
        logger::error("FX set {} not found", a_set.c_str());
        return 0;
    }

    const FurnitureDetails* Library::GetFurnitureDetails(const RE::TESObjectREFR* a_ref) const
    {
        if (!a_ref)
            return nullptr;
        if (a_ref->Is(RE::FormType::ActorCharacter)) {
            return nullptr;
        }
        const auto ref = a_ref->GetObjectReference();
        if (const auto tesmodel = ref ? ref->As<RE::TESModel>() : nullptr) {
            std::shared_lock lock{ _mFurniture };
            const auto where = furnitures.find(tesmodel->model);
            if (where != furnitures.end()) {
                return where->second.get();
            }
        }
        switch (FurnitureType::GetBedType(a_ref)) {
        case FurnitureType::BedSingle:
            return &offsetDefaultBedsingle;
        case FurnitureType::BedDouble:
            return &offsetDefaultBeddouble;
        case FurnitureType::BedRoll:
            return &offsetDefaultBedroll;
        }
        return nullptr;
    }
}
