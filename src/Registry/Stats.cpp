#include "Stats.h"

#include "Registry/Define/RaceKey.h"
#include "Registry/Define/Sex.h"

namespace Registry::Statistics
{
    namespace
    {
        template <class T>
        T ReadStatisticsValue(SKSE::SerializationInterface* a_intfc, uint32_t& a_remaining)
        {
            T value{};
            if (sizeof(T) > a_remaining || a_intfc->ReadRecordData(value) != sizeof(T))
                throw std::runtime_error("Truncated statistics record");
            a_remaining -= static_cast<uint32_t>(sizeof(T));
            return value;
        }

        std::string ReadStatisticsString(SKSE::SerializationInterface* a_intfc, uint32_t& a_remaining)
        {
            const auto size = ReadStatisticsValue<size_t>(a_intfc, a_remaining);
            if (!size || size > a_remaining)
                throw std::runtime_error("Invalid statistics string length");
            std::string value(size, '\0');
            if (a_intfc->ReadRecordData(value.data(), static_cast<uint32_t>(size)) != size || value.back() != '\0')
                throw std::runtime_error("Invalid statistics string payload");
            a_remaining -= static_cast<uint32_t>(size);
            value.resize(size - 1);
            return value;
        }
    }

    ActorStats::ActorStats(RE::Actor* owner) :
      _stats(StatisticID::Total)
    {
        const auto base = owner->GetActorBase();
        if (const auto relations = base ? base->relationships : nullptr) {
            Registry::Sexuality s = Sexuality::None;
            for (auto&& rs : *relations) {
                if (!rs)
                    continue;
                if (!rs->level.all(RE::BGSRelationship::RELATIONSHIP_LEVEL::kLover))
                    continue;
                const auto other = rs->npc1 == base ? rs->npc2 : rs->npc1;
                if (!other)
                    continue;
                bool samesex = base->GetSex() == other->GetSex();
                switch (s) {
                case Sexuality::Hetero:
                    if (samesex) {
                        s = Sexuality::Bi;
                        break;
                    }
                    continue;  // Next iteration
                case Sexuality::Homo:
                    if (!samesex) {
                        s = Sexuality::Bi;
                        break;
                    }
                    continue;
                default:
                    s = samesex ? Sexuality::Homo : Sexuality::Hetero;
                    continue;
                }
                break;
            }
            if (s != Sexuality::Bi && s != Sexuality::None) {
                const auto chance = s == Sexuality::Hetero ?
                                        Settings::fPercentageHetero + (Settings::fPercentageHomo / 2) :
                                        Settings::fPercentageHomo + (Settings::fPercentageHetero / 2);
                if (chance >= Random::draw<float>(0, 99)) {
                    s = Sexuality::Bi;
                }
            }
            switch (s) {
            case Sexuality::Bi:
                _stats[StatisticID::Sexuality] = owner->IsPlayerRef() ? 75.0f : Random::draw(Settings::fPercentageHomo, 100.0f - Settings::fPercentageHetero);
                break;
            case Sexuality::Hetero:
                _stats[StatisticID::Sexuality] = Random::draw(100.0f - Settings::fPercentageHetero, 100.0f);
                break;
            case Sexuality::Homo:
                _stats[StatisticID::Sexuality] = Random::draw(1.0f, Settings::fPercentageHomo);
                break;
            default:
                _stats[StatisticID::Sexuality] = Random::draw(1.0f, 100.0f);
                break;
            }
        } else {
            _stats[StatisticID::Sexuality] = owner->IsPlayerRef() ? 75.0f : Random::draw(1.0f, 100.0f);
        }
    }

    ActorStats::ActorStats(SKSE::SerializationInterface* a_intfc, uint32_t a_version, uint32_t& a_remaining) :
      _stats(StatisticID::Total), _custom({})
    {
        for (size_t i = 0; i < StatisticID::Total; i++) {
            _stats[i] = ReadStatisticsValue<float>(a_intfc, a_remaining);
        }
        const auto numRegs = ReadStatisticsValue<size_t>(a_intfc, a_remaining);
        for (size_t i = 0; i < numRegs; i++) {
            const auto key = ReadStatisticsString(a_intfc, a_remaining);
            const auto alternative = ReadStatisticsValue<uint32_t>(a_intfc, a_remaining);
            if (alternative == 0) {
                float obj{};
                if (a_version == 1) {
                    // Version 1's MSVC x64 writer dumped the variant object.
                    // Measured with CommonLib's BSFixedString: 16 bytes, float at offset 0.
                    // Padding is ignored; no serialized pointer is ever dereferenced.
                    static_assert(sizeof(std::variant<float, RE::BSFixedString>) == 16);
                    const auto legacy = ReadStatisticsValue<std::array<std::byte, 16>>(a_intfc, a_remaining);
                    std::memcpy(&obj, legacy.data(), sizeof(obj));
                } else {
                    obj = ReadStatisticsValue<float>(a_intfc, a_remaining);
                }
                _custom[key] = obj;
            } else if (alternative == 1) {
                _custom[key] = RE::BSFixedString{ ReadStatisticsString(a_intfc, a_remaining) };
            } else {
                throw std::runtime_error("Invalid statistics variant tag");
            }
        }
    }

    void ActorStats::SetStatistic(StatisticID key, float value)
    {
        _stats[key] = value;
    }

    void ActorStats::AddStatistic(StatisticID key, float value)
    {
        _stats[key] += value;
    }

    float ActorStats::GetStatistic(StatisticID key) const
    {
        return _stats[key];
    }

    std::vector<RE::BSFixedString> ActorStats::GetEveryCustomID() const
    {
        const auto v = std::views::keys(_custom);
        return std::vector<RE::BSFixedString>{ v.begin(), v.end() };
    }

    std::optional<float> ActorStats::GetCustomFlt(const RE::BSFixedString& key) const
    {
        return GetCustom<float>(key);
    }

    std::optional<RE::BSFixedString> ActorStats::GetCustomStr(const RE::BSFixedString& key) const
    {
        return GetCustom<RE::BSFixedString>(key);
    }

    void ActorStats::SetCustomFlt(const RE::BSFixedString& key, float value)
    {
        _custom[key] = value;
    }

    void ActorStats::SetCustomStr(const RE::BSFixedString& key, RE::BSFixedString value)
    {
        _custom[key] = value;
    }

    bool ActorStats::HasCustom(const RE::BSFixedString& key) const
    {
        return _custom.contains(key);
    }

    void ActorStats::RemoveCustomStat(const RE::BSFixedString& key)
    {
        _custom.erase(key);
    }

    void ActorStats::Save(SKSE::SerializationInterface* a_intfc)
    {
        for (auto stat : _stats) {
            if (!a_intfc->WriteRecordData(stat))
                throw std::runtime_error("Failed to save statistic");
        }
        if (!a_intfc->WriteRecordData(_custom.size()))
            throw std::runtime_error("Failed to save custom statistic count");
        for (const auto& [id, stat] : _custom) {
            if (!stl::write_string(a_intfc, id) || !a_intfc->WriteRecordData(static_cast<uint32_t>(stat.index())))
                throw std::runtime_error("Failed to save custom statistic key or type");
            if (const auto number = std::get_if<float>(&stat)) {
                if (!a_intfc->WriteRecordData(*number))
                    throw std::runtime_error("Failed to save numeric statistic");
            } else if (!stl::write_string(a_intfc, std::get<RE::BSFixedString>(stat))) {
                throw std::runtime_error("Failed to save string statistic");
            }
        }
    }

    ActorEncounter::EncounterObj::EncounterObj(RE::Actor* obj) :
      id(obj->GetFormID()), race(obj), sex(Registry::GetSex(obj)) {}

    ActorEncounter::EncounterObj::EncounterObj(SKSE::SerializationInterface* a_intfc, uint32_t& a_remaining)
    {
        const auto savedID = ReadStatisticsValue<RE::FormID>(a_intfc, a_remaining);
        race = ReadStatisticsValue<RaceKey::Value>(a_intfc, a_remaining);
        sex = ReadStatisticsValue<Sex>(a_intfc, a_remaining);
        if (!a_intfc->ResolveFormID(savedID, id))
            id = 0;
    }

    void ActorEncounter::EncounterObj::Save(SKSE::SerializationInterface* a_intfc)
    {
        if (!a_intfc->WriteRecordData(id) || !a_intfc->WriteRecordData(race.value) || !a_intfc->WriteRecordData(sex))
            throw std::runtime_error("Failed to save encounter participant");
    }

    ActorEncounter::ActorEncounter(RE::Actor* fst, RE::Actor* snd, EncounterType a_type) :
      npc1(fst), npc2(snd), _lastmet(0), _timesmet(0), _timessubmissive(0), _timesdominant(0), _timesvictim(0), _timesaggressor(0)
    {
        Update(a_type);
    }

    ActorEncounter::ActorEncounter(SKSE::SerializationInterface* a_intfc, uint32_t& a_remaining, bool a_legacyCounts) :
      npc1(a_intfc, a_remaining), npc2(a_intfc, a_remaining)
    {
        _lastmet = ReadStatisticsValue<float>(a_intfc, a_remaining);
        for (auto* count : { &_timesmet, &_timesaggressor, &_timesvictim, &_timesdominant, &_timessubmissive }) {
            *count = a_legacyCounts ? ReadStatisticsValue<uint8_t>(a_intfc, a_remaining) : ReadStatisticsValue<int32_t>(a_intfc, a_remaining);
            if (*count < 0)
                throw std::runtime_error("Invalid encounter count");
        }
    }

    const ActorEncounter::EncounterObj* ActorEncounter::GetPartner(RE::Actor* a_actor) const
    {
        if (a_actor->formID == npc1.id)
            return &npc2;
        if (a_actor->formID == npc2.id)
            return &npc1;
        return nullptr;
    }

    int32_t ActorEncounter::GetTimesSubmissive(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timessubmissive :
               a_id == npc2.id ? _timesdominant :
                                 0;
    }

    int32_t ActorEncounter::GetTimesDominant(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesdominant :
               a_id == npc2.id ? _timessubmissive :
                                 0;
    }

    int32_t ActorEncounter::GetTimesVictim(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesvictim :
               a_id == npc2.id ? _timesaggressor :
                                 0;
    }

    int32_t ActorEncounter::GetTimesAssailant(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesaggressor :
               a_id == npc2.id ? _timesvictim :
                                 0;
    }

    void ActorEncounter::Update(EncounterType a_type)
    {
        _lastmet = RE::Calendar::GetSingleton()->GetCurrentGameTime();
        const auto increment = [](int32_t& count) {
            if (count < (std::numeric_limits<int32_t>::max)())
                ++count;
        };
        increment(_timesmet);
        switch (a_type) {
        case EncounterType::Aggressor:
            increment(_timesaggressor);
            __fallthrough;
        case EncounterType::Dominant:
            increment(_timesdominant);
            break;
        case EncounterType::Victim:
            increment(_timesvictim);
            __fallthrough;
        case EncounterType::Submissive:
            increment(_timessubmissive);
            break;
        }
    }

    void ActorEncounter::Save(SKSE::SerializationInterface* a_intfc)
    {
        npc1.Save(a_intfc);
        npc2.Save(a_intfc);
        if (!a_intfc->WriteRecordData(_lastmet))
            throw std::runtime_error("Failed to save encounter time");
        for (auto count : { _timesmet, _timesaggressor, _timesvictim, _timesdominant, _timessubmissive }) {
            if (!a_intfc->WriteRecordData(count))
                throw std::runtime_error("Failed to save encounter count");
        }
    }

    void StatisticsData::Register()
    {
        const auto script = RE::ScriptEventSourceHolder::GetSingleton();
        script->AddEventSink<RE::TESDeathEvent>(this);
        script->AddEventSink<RE::TESResetEvent>(this);
    }

    std::vector<RE::Actor*> StatisticsData::GetTrackedActors() const
    {
        const std::shared_lock lock{ _m };
        std::vector<RE::Actor*> ret{};
        ret.reserve(_data.size());
        for (auto&& [id, _] : _data) {
            const auto act = RE::TESForm::LookupByID<RE::Actor>(id);
            if (!act)
                continue;
            ret.push_back(act);
        }
        return ret;
    }

    StatisticsData::StatisticsAccess StatisticsData::GetStatistics(RE::Actor* a_key)
    {
        std::unique_lock lock{ _m };
        auto where = _data.find(a_key->GetFormID());
        if (where == _data.end()) {
            _data.insert(std::make_pair(a_key->GetFormID(), ActorStats{ a_key }));
            return { std::move(lock), _data.at(a_key->GetFormID()) };
        }
        return { std::move(lock), where->second };
    }

    std::optional<ActorEncounter> StatisticsData::GetEncounter(RE::Actor* fst, RE::Actor* snd)
    {
        const std::shared_lock lock{ _m };
        const auto where = GetEncounterIter(fst, snd);
        return where == _encounters.end() ? std::nullopt : std::optional<ActorEncounter>{ *where };
    }

    std::vector<ActorEncounter>::iterator StatisticsData::GetEncounterIter(RE::Actor* fst, RE::Actor* snd)
    {
        return std::ranges::find_if(_encounters, [&](const ActorEncounter& enc) {
            const auto& [a, b] = enc.GetParticipants();
            return a.id == fst->formID && b.id == snd->formID || b.id == fst->formID && a.id == snd->formID;
        });
    }

    void StatisticsData::DeleteStatistics(RE::FormID a_key)
    {
        const std::unique_lock lock{ _m };
        _data.erase(a_key);
        std::erase_if(_encounters, [&](auto& encounter) {
            const auto [fst, snd] = encounter.GetParticipants();
            return fst.id == a_key || snd.id == a_key;
        });
    }

    bool StatisticsData::ForEachStatistic(std::function<bool(ActorStats&)> a_func)
    {
        const std::unique_lock lock{ _m };
        for (auto&& [_, statistic] : _data) {
            if (a_func(statistic))
                return true;
        }
        return false;
    }

    bool StatisticsData::ForEachEncounter(std::function<bool(ActorEncounter&)> a_func)
    {
        const std::unique_lock lock{ _m };
        for (auto&& encounter : _encounters) {
            if (a_func(encounter))
                return true;
        }
        return false;
    }

    void StatisticsData::AddEncounter(RE::Actor* fst, RE::Actor* snd, ActorEncounter::EncounterType a_type)
    {
        const std::unique_lock lock{ _m };
        if (auto enc = GetEncounterIter(fst, snd); enc != _encounters.end()) {
            if (enc->GetParticipants().first.id == snd->formID) {
                switch (a_type) {
                case ActorEncounter::EncounterType::Aggressor:
                    a_type = ActorEncounter::EncounterType::Victim;
                    break;
                case ActorEncounter::EncounterType::Victim:
                    a_type = ActorEncounter::EncounterType::Aggressor;
                    break;
                case ActorEncounter::EncounterType::Submissive:
                    a_type = ActorEncounter::EncounterType::Dominant;
                    break;
                case ActorEncounter::EncounterType::Dominant:
                    a_type = ActorEncounter::EncounterType::Submissive;
                    break;
                default:
                    a_type = ActorEncounter::EncounterType::Any;
                    break;
                }
            }
            enc->Update(a_type);
            std::rotate(enc, std::next(enc), _encounters.end());
            return;
        }
        _encounters.emplace_back(fst, snd, a_type);
    }

    RE::Actor* StatisticsData::GetMostRecentEncounter(RE::Actor* a_actor, ActorEncounter::EncounterType a_type)
    {
        const std::shared_lock lock{ _m };
        for (auto it = _encounters.rbegin(); it != _encounters.rend(); it++) {
            const auto partnerobj = it->GetPartner(a_actor);
            const auto partner = partnerobj ? RE::TESForm::LookupByID<RE::Actor>(partnerobj->id) : nullptr;
            if (!partner)
                continue;
            switch (a_type) {
            case ActorEncounter::EncounterType::Any:
                return partner;
            case ActorEncounter::EncounterType::Victim:
                if (it->GetTimesVictim(a_actor->formID) > 0) {
                    return partner;
                }
                break;
            case ActorEncounter::EncounterType::Aggressor:
                if (it->GetTimesAssailant(a_actor->formID) > 0) {
                    return partner;
                }
                break;
            case ActorEncounter::EncounterType::Submissive:
                if (it->GetTimesSubmissive(a_actor->formID) > 0) {
                    return partner;
                }
                break;
            case ActorEncounter::EncounterType::Dominant:
                if (it->GetTimesDominant(a_actor->formID) > 0) {
                    return partner;
                }
                break;
            }
        }
        return nullptr;
    }

    int StatisticsData::GetNumberEncounters(RE::Actor* a_actor)
    {
        return GetNumberEncounters(a_actor, ActorEncounter::EncounterType::Any, [](auto&) { return true; });
    }
    int StatisticsData::GetNumberEncounters(RE::Actor* a_actor, ActorEncounter::EncounterType a_type)
    {
        return GetNumberEncounters(a_actor, a_type, [](auto&) { return true; });
    }
    int StatisticsData::GetNumberEncounters(RE::Actor* a_actor, std::function<bool(const ActorEncounter::EncounterObj&)> a_pred)
    {
        return GetNumberEncounters(a_actor, ActorEncounter::EncounterType::Any, a_pred);
    }
    int StatisticsData::GetNumberEncounters(RE::Actor* a_actor, ActorEncounter::EncounterType a_type, std::function<bool(const ActorEncounter::EncounterObj&)> a_pred)
    {
        const std::shared_lock lock{ _m };
        int64_t ret = 0;
        for (auto&& encounter : _encounters) {
            const auto partner = encounter.GetPartner(a_actor);
            if (!partner || !a_pred(*partner))
                continue;
            switch (a_type) {
            case ActorEncounter::EncounterType::Any:
                ret += encounter.GetTimesMet();
                break;
            case ActorEncounter::EncounterType::Victim:
                ret += encounter.GetTimesVictim(a_actor->formID);
                break;
            case ActorEncounter::EncounterType::Aggressor:
                ret += encounter.GetTimesAssailant(a_actor->formID);
                break;
            case ActorEncounter::EncounterType::Submissive:
                ret += encounter.GetTimesSubmissive(a_actor->formID);
                break;
            case ActorEncounter::EncounterType::Dominant:
                ret += encounter.GetTimesDominant(a_actor->formID);
                break;
            }
        }
        return static_cast<int>(std::min<int64_t>(ret, (std::numeric_limits<int>::max)()));
    }

    StatisticsData::EventResult StatisticsData::ProcessEvent(const RE::TESDeathEvent* a_event, RE::BSTEventSource<RE::TESDeathEvent>*)
    {
        if (!a_event || !a_event->actorDying)
            return EventResult::kContinue;

        DeleteStatistics(a_event->actorDying->formID);
        return EventResult::kContinue;
    }

    StatisticsData::EventResult StatisticsData::ProcessEvent(const RE::TESResetEvent* a_event, RE::BSTEventSource<RE::TESResetEvent>*)
    {
        if (!a_event || !a_event->object || a_event->object->IsNot(RE::FormType::ActorCharacter))
            return EventResult::kContinue;

        DeleteStatistics(a_event->object->formID);
        return EventResult::kContinue;
    }

    void StatisticsData::Save(SKSE::SerializationInterface* a_intfc)
    {
        const std::shared_lock lock{ _m };
        try {
            if (!a_intfc->WriteRecordData(_data.size()))
                throw std::runtime_error("Failed to save statistics count");
            for (auto&& [id, data] : _data) {
                if (!a_intfc->WriteRecordData(id))
                    throw std::runtime_error("Failed to save statistics actor");
                data.Save(a_intfc);
            }
        } catch (const std::exception& e) {
            logger::error("{}", e.what());
            return;
        }
        logger::info("Saved {} statistics", _data.size());
    }

    void StatisticsData::Load(SKSE::SerializationInterface* a_intfc, uint32_t a_version, uint32_t a_length)
    {
        const std::unique_lock lock{ _m };
        if (a_version != 1 && a_version != 2)
            return;
        decltype(_data) loaded;
        try {
            const auto numRegs = ReadStatisticsValue<size_t>(a_intfc, a_length);
            for (size_t i = 0; i < numRegs; i++) {
                auto formID = ReadStatisticsValue<RE::FormID>(a_intfc, a_length);
                // Consume the complete entry even when its owning plugin is missing.
                ActorStats stats{ a_intfc, a_version, a_length };
                if (!a_intfc->ResolveFormID(formID, formID)) {
                    logger::warn("Error resolving statistics formID ({:X})", formID);
                    continue;
                }
                loaded.emplace(formID, std::move(stats));
            }
            // Some v2 fork builds appended encounter history using byte-sized counters.
            if (a_version == 2 && a_length) {
                std::vector<ActorEncounter> encounters;
                const auto count = ReadStatisticsValue<uint64_t>(a_intfc, a_length);
                for (uint64_t i = 0; i < count; ++i) {
                    ActorEncounter encounter{ a_intfc, a_length, true };
                    const auto [first, second] = encounter.GetParticipants();
                    if (first.id && second.id)
                        encounters.push_back(std::move(encounter));
                }
                if (a_length)
                    throw std::runtime_error("Unexpected trailing v2 encounter data");
                _encounters.swap(encounters);
            } else if (a_length) {
                throw std::runtime_error("Unexpected trailing statistics data");
            }
        } catch (const std::exception& e) {
            logger::error("Unable to load statistics record version {}: {}", a_version, e.what());
            return;
        }
        _data.swap(loaded);
        logger::info("Loaded {} statistics", _data.size());
    }

    void StatisticsData::SaveEncounters(SKSE::SerializationInterface* a_intfc)
    {
        const std::shared_lock lock{ _m };
        try {
            if (!a_intfc->WriteRecordData(_encounters.size()))
                throw std::runtime_error("Failed to save encounter history length");
            for (auto& encounter : _encounters)
                encounter.Save(a_intfc);
        } catch (const std::exception& e) {
            logger::error("{}", e.what());
        }
    }

    void StatisticsData::LoadEncounters(SKSE::SerializationInterface* a_intfc, uint32_t a_length)
    {
        const std::unique_lock lock{ _m };
        std::vector<ActorEncounter> encounters;
        try {
            const auto count = ReadStatisticsValue<size_t>(a_intfc, a_length);
            for (size_t i = 0; i < count; ++i) {
                ActorEncounter encounter{ a_intfc, a_length };
                const auto [first, second] = encounter.GetParticipants();
                if (first.id && second.id)
                    encounters.push_back(std::move(encounter));
            }
            if (a_length)
                throw std::runtime_error("Unexpected trailing encounter data");
        } catch (const std::exception& e) {
            logger::error("Unable to load encounter history: {}", e.what());
            return;
        }
        _encounters.swap(encounters);
    }

    void StatisticsData::Revert(SKSE::SerializationInterface*)
    {
        const std::unique_lock lock{ _m };
        _data.clear();
        _encounters.clear();
    }


}  // namespace Registry::Statistics
