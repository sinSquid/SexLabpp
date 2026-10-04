#include "Stats.h"

#include "Registry/Define/RaceKey.h"
#include "Registry/Define/Sex.h"

namespace Registry::Statistics
{
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
                _stats[StatisticID::Sexuality] = Random::draw(0.0f, Settings::fPercentageHomo);
                break;
            default:
                _stats[StatisticID::Sexuality] = Random::draw(1.0f, 100.0f);
                break;
            }
        } else {
            _stats[StatisticID::Sexuality] = owner->IsPlayerRef() ? 75.0f : Random::draw(1.0f, 100.0f);
        }
    }

    ActorStats::ActorStats(Util::RecordReader<SKSE::SerializationInterface>& reader, uint32_t version) :
      _stats(StatisticID::Total)
    {
        for (auto& stat : _stats)
            stat = reader.Read<float>();
        const auto count = reader.Count(13);
        for (uint64_t i = 0; i < count; ++i) {
            const auto key = reader.String();
            const auto type = reader.Read<uint32_t>();
            if (type == 0) {
                float value;
                if (version == 1) {
                    // v1 wrote MSVC x64 variant<float, BSFixedString> (16 bytes):
                    // storage at offset 0 and alternative index at offset 8.
                    std::array<uint8_t, 16> legacy{};
                    reader.Bytes(legacy.data(), static_cast<uint32_t>(legacy.size()));
                    if (legacy[8] != 0)
                        throw std::runtime_error("Unsupported legacy statistics variant layout");
                    std::memcpy(&value, legacy.data(), sizeof(value));
                } else {
                    value = reader.Read<float>();
                }
                _custom[RE::BSFixedString(key)] = value;
            } else if (type == 1) {
                _custom[RE::BSFixedString(key)] = RE::BSFixedString(reader.String());
            } else {
                throw std::runtime_error("Invalid custom statistic type");
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
        for (const auto stat : _stats)
            Util::WriteRecord(a_intfc, stat);
        Util::WriteRecord(a_intfc, static_cast<uint64_t>(_custom.size()));
        for (const auto& [id, stat] : _custom) {
            Util::WriteRecordString(a_intfc, id);
            Util::WriteRecord(a_intfc, static_cast<uint32_t>(stat.index()));
            if (const auto value = std::get_if<float>(&stat))
                Util::WriteRecord(a_intfc, *value);
            else
                Util::WriteRecordString(a_intfc, std::get<RE::BSFixedString>(stat));
        }
    }

    ActorEncounter::EncounterObj::EncounterObj(RE::Actor* obj) :
      id(obj->GetFormID()), race(obj), sex(Registry::GetSex(obj)) {}

    ActorEncounter::EncounterObj::EncounterObj(Util::RecordReader<SKSE::SerializationInterface>& reader) :
      id(reader.Read<uint32_t>()), race(static_cast<RaceKey::Value>(reader.Read<uint8_t>())), sex(static_cast<Sex>(reader.Read<uint8_t>()))
    {}

    void ActorEncounter::EncounterObj::Save(SKSE::SerializationInterface* a_intfc)
    {
        Util::WriteRecord(a_intfc, id);
        Util::WriteRecord(a_intfc, static_cast<uint8_t>(race.value));
        Util::WriteRecord(a_intfc, static_cast<uint8_t>(sex));
    }

    ActorEncounter::ActorEncounter(RE::Actor* fst, RE::Actor* snd, EncounterType a_type) :
      npc1(fst), npc2(snd), _lastmet(0), _timesmet(0), _timesaggressor(0), _timesvictim(0)
    {
        Update(a_type);
    }

    ActorEncounter::ActorEncounter(Util::RecordReader<SKSE::SerializationInterface>& reader) :
      npc1(reader), npc2(reader)
    {
        _lastmet = reader.Read<float>();
        _timesmet = reader.Read<uint8_t>();
        _timesaggressor = reader.Read<uint8_t>();
        _timesvictim = reader.Read<uint8_t>();
        _timesdominant = reader.Read<uint8_t>();
        _timessubmissive = reader.Read<uint8_t>();
    }

    bool ActorEncounter::Resolve(SKSE::SerializationInterface* a_intfc)
    {
        return a_intfc->ResolveFormID(npc1.id, npc1.id) && a_intfc->ResolveFormID(npc2.id, npc2.id);
    }

    const ActorEncounter::EncounterObj* ActorEncounter::GetPartner(RE::Actor* a_actor) const
    {
        if (a_actor->formID == npc1.id)
            return &npc2;
        if (a_actor->formID == npc2.id)
            return &npc1;
        return nullptr;
    }

    uint8_t ActorEncounter::GetTimesSubmissive(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timessubmissive :
               a_id == npc2.id ? _timesdominant :
                                 0;
    }

    uint8_t ActorEncounter::GetTimesDominant(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesdominant :
               a_id == npc2.id ? _timessubmissive :
                                 0;
    }

    uint8_t ActorEncounter::GetTimesVictim(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesvictim :
               a_id == npc2.id ? _timesaggressor :
                                 0;
    }

    uint8_t ActorEncounter::GetTimesAssailant(RE::FormID a_id) const
    {
        return a_id == npc1.id ? _timesaggressor :
               a_id == npc2.id ? _timesvictim :
                                 0;
    }

    void ActorEncounter::Update(EncounterType a_type)
    {
        _lastmet = RE::Calendar::GetSingleton()->GetCurrentGameTime();
        const auto increment = [](uint8_t& count) { if (count < 255) ++count; };
        increment(_timesmet);
        switch (a_type) {
        case EncounterType::Any:
            break;
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
        Util::WriteRecord(a_intfc, _lastmet);
        Util::WriteRecord(a_intfc, _timesmet);
        Util::WriteRecord(a_intfc, _timesaggressor);
        Util::WriteRecord(a_intfc, _timesvictim);
        Util::WriteRecord(a_intfc, _timesdominant);
        Util::WriteRecord(a_intfc, _timessubmissive);
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

    StatisticsData::LockedStatistics StatisticsData::GetStatistics(RE::Actor* a_key)
    {
        std::unique_lock lock{ _m };
        auto [it, inserted] = _data.try_emplace(a_key->GetFormID(), a_key);
        return { std::move(lock), it->second };
    }

    ActorStats StatisticsData::GetStatisticsSnapshot(RE::Actor* a_key)
    {
        const auto locked = GetStatistics(a_key);
        return *locked;
    }

    std::optional<ActorEncounter> StatisticsData::GetEncounter(RE::Actor* fst, RE::Actor* snd)
    {
        const std::shared_lock lock{ _m };
        const auto where = GetEncounterIter(fst, snd);
        if (where == _encounters.end())
            return std::nullopt;
        return *where;
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
                case ActorEncounter::EncounterType::Dominant:
                    a_type = ActorEncounter::EncounterType::Submissive;
                    break;
                case ActorEncounter::EncounterType::Submissive:
                    a_type = ActorEncounter::EncounterType::Dominant;
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
        int ret = 0;
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
        return ret;
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
            Util::WriteRecord(a_intfc, static_cast<uint64_t>(_data.size()));
            for (auto& [id, data] : _data) {
                Util::WriteRecord(a_intfc, id);
                data.Save(a_intfc);
            }
            Util::WriteRecord(a_intfc, static_cast<uint64_t>(_encounters.size()));
            for (auto& encounter : _encounters)
                encounter.Save(a_intfc);
        } catch (const std::exception& e) {
            logger::error("Statistics save failed: {}", e.what());
        }
    }

    void StatisticsData::Load(SKSE::SerializationInterface* a_intfc, uint32_t version, uint32_t length)
    {
        std::map<RE::FormID, ActorStats> data;
        std::vector<ActorEncounter> encounters;
        try {
            Util::RecordReader reader(a_intfc, length);
            const auto count = reader.Count(4 + 4 * ActorStats::Total + 8);
            for (uint64_t i = 0; i < count; ++i) {
                auto id = reader.Read<uint32_t>();
                ActorStats value(reader, version);  // consume even when the form no longer exists
                if (a_intfc->ResolveFormID(id, id))
                    data.insert_or_assign(id, std::move(value));
            }
            if (version >= 2) {
                const auto countEncounters = reader.Count(21);
                for (uint64_t i = 0; i < countEncounters; ++i) {
                    ActorEncounter value(reader);
                    if (value.Resolve(a_intfc))
                        encounters.push_back(std::move(value));
                }
            }
            if (reader.Remaining() != 0)
                throw std::runtime_error("Unexpected trailing statistics data");
        } catch (const std::exception& e) {
            logger::error("Statistics record rejected (version {}): {}", version, e.what());
            data.clear();
            encounters.clear();
        }
        const std::unique_lock lock{ _m };
        _data = std::move(data);
        _encounters = std::move(encounters);
    }

    void StatisticsData::Revert(SKSE::SerializationInterface*)
    {
        const std::unique_lock lock{ _m };
        _data.clear();
        _encounters.clear();
    }


}  // namespace Registry::Statistics
