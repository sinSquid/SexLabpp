#pragma once

namespace Papyrus
{
    class Tracking :
      public Singleton<Tracking>
    {
      public:
        mutable std::shared_mutex _mutex;
        std::map<RE::FormID, std::vector<RE::BSFixedString>> _factions;
        std::map<RE::FormID, std::vector<RE::BSFixedString>> _actors;

      public:
        void Add(std::map<RE::FormID, std::vector<RE::BSFixedString>>& a_list, RE::FormID a_keyvalue, const RE::BSFixedString& a_callback)
        {
            const std::unique_lock lock{ _mutex };
            auto it = a_list.find(a_keyvalue);
            if (it == a_list.end()) {
                a_list.insert({ a_keyvalue, { a_callback } });
            } else if (std::find(it->second.begin(), it->second.end(), a_callback) == it->second.end()) {
                it->second.push_back(a_callback);
            }
        }

        void Remove(std::map<RE::FormID, std::vector<RE::BSFixedString>>& a_list, RE::FormID a_keyvalue, const RE::BSFixedString& a_callback)
        {
            const std::unique_lock lock{ _mutex };
            auto it = a_list.find(a_keyvalue);
            if (it == a_list.end())
                return;

            const auto where = std::remove(it->second.begin(), it->second.end(), a_callback);
            if (where == it->second.begin()) {
                a_list.erase(it);
            } else {
                it->second.erase(where, it->second.end());
            }
        }

      public:
        void Save(SKSE::SerializationInterface* a_intfc)
        {
            const std::shared_lock lock{ _mutex };
            const auto save = [&](const auto& entries) {
                if (!a_intfc->WriteRecordData(entries.size()))
                    return false;
                for (const auto& [id, events] : entries) {
                    if (!a_intfc->WriteRecordData(id) || !a_intfc->WriteRecordData(events.size()))
                        return false;
                    for (const auto& event : events) {
                        if (!stl::write_string(a_intfc, event))
                            return false;
                    }
                    if (!a_intfc->WriteRecordData((std::numeric_limits<uint32_t>::max)()))
                        return false;
                }
                return true;
            };
            if (!save(_factions) || !save(_actors)) {
                logger::error("Failed to write tracking record");
                return;
            }
            logger::info("Saved {} tracked factions and {} actors", _factions.size(), _actors.size());
        }

        void Load(SKSE::SerializationInterface* a_intfc, uint32_t remaining)
        {
            const std::unique_lock lock{ _mutex };
            const auto read = [&]<class T>(T& value) {
                if (remaining < sizeof(T) || a_intfc->ReadRecordData(value) != sizeof(T))
                    throw std::runtime_error("Truncated tracking record");
                remaining -= static_cast<uint32_t>(sizeof(T));
            };

            const auto load = [&](auto& entries) {
                size_t numRegs{};
                read(numRegs);
                for (size_t i = 0; i < numRegs; ++i) {
                    RE::FormID id{};
                    read(id);
                    size_t numEvents{};
                    read(numEvents);
                    if (numEvents > remaining / (sizeof(size_t) + 1))
                        throw std::runtime_error("Invalid tracking event count");
                    std::vector<RE::BSFixedString> list;
                    for (size_t n = 0; n < numEvents; ++n) {
                        size_t length{};
                        read(length);
                        if (!length || length > remaining)
                            throw std::runtime_error("Invalid tracking event length");
                        std::string event(length, '\0');
                        const auto size = static_cast<uint32_t>(length);
                        if (a_intfc->ReadRecordData(event.data(), size) != size || event.back() != '\0')
                            throw std::runtime_error("Invalid tracking event payload");
                        remaining -= size;
                        event.pop_back();
                        list.emplace_back(event);
                    }
                    uint32_t marker{};
                    read(marker);
                    if (marker != (std::numeric_limits<uint32_t>::max)())
                        throw std::runtime_error("Invalid tracking record marker");
                    RE::FormID resolved{};
                    if (a_intfc->ResolveFormID(id, resolved))
                        entries.emplace(resolved, std::move(list));
                }
            };

            decltype(_factions) factions;
            decltype(_actors) actors;
            try {
                load(factions);
                load(actors);
                if (remaining)
                    throw std::runtime_error("Trailing tracking record data");
            } catch (const std::exception& error) {
                logger::error("Unable to load tracking record: {}", error.what());
                return;
            }
            _factions.swap(factions);
            _actors.swap(actors);
            logger::info("Loaded {} tracked factions and {} actors", _factions.size(), _actors.size());
        }

        void Revert(SKSE::SerializationInterface*)
        {
            const std::unique_lock lock{ _mutex };
            _factions.clear();
            _actors.clear();
        }
    };

}  // namespace Papyrus
