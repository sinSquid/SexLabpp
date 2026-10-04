#pragma once
#include "Util/RecordIO.h"
#include <shared_mutex>

namespace Papyrus
{
    class Tracking :
      public Singleton<Tracking>
    {
      public:
        std::map<RE::FormID, std::vector<RE::BSFixedString>> _factions;
        std::map<RE::FormID, std::vector<RE::BSFixedString>> _actors;

      private:
        mutable std::shared_mutex _mutex;

      public:
        using Registrations = std::map<RE::FormID, std::vector<RE::BSFixedString>>;
        bool Contains(const Registrations& list, RE::FormID id) const
        {
            std::shared_lock lock{ _mutex };
            return list.contains(id);
        }
        std::vector<RE::BSFixedString> Callbacks(const Registrations& list, RE::FormID id) const
        {
            std::shared_lock lock{ _mutex };
            const auto it = list.find(id);
            return it == list.end() ? std::vector<RE::BSFixedString>{} : it->second;
        }
        void Add(std::map<RE::FormID, std::vector<RE::BSFixedString>>& a_list, RE::FormID a_keyvalue, const RE::BSFixedString& a_callback)
        {
            std::unique_lock lock{ _mutex };
            auto it = a_list.find(a_keyvalue);
            if (it == a_list.end()) {
                a_list.insert({ a_keyvalue, { a_callback } });
            } else if (std::find(it->second.begin(), it->second.end(), a_callback) == it->second.end()) {
                it->second.push_back(a_callback);
            }
        }

        void Remove(std::map<RE::FormID, std::vector<RE::BSFixedString>>& a_list, RE::FormID a_keyvalue, const RE::BSFixedString& a_callback)
        {
            std::unique_lock lock{ _mutex };
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
            std::shared_lock lock{ _mutex };
            try {
                const auto save = [&](const Registrations& entries) {
                    Util::WriteRecord(a_intfc, static_cast<uint64_t>(entries.size()));
                    for (const auto& [id, callbacks] : entries) {
                        Util::WriteRecord(a_intfc, id);
                        Util::WriteRecord(a_intfc, static_cast<uint64_t>(callbacks.size()));
                        for (const auto& callback : callbacks) Util::WriteRecordString(a_intfc, callback);
                        Util::WriteRecord(a_intfc, UINT32_MAX);
                    }
                };
                save(_factions);
                save(_actors);
                logger::info("Saved {} tracked factions and {} actors", _factions.size(), _actors.size());
            } catch (const std::exception& error) {
                logger::error("Tracking save failed: {}", error.what());
            }
        }

        // Version 1 keeps its existing x64 wire format: uint64 counts, uint32 IDs,
        // terminated strings and UINT32_MAX entry delimiters.
        void Load(SKSE::SerializationInterface* a_intfc, uint32_t length)
        {
            Registrations factions, actors;
            try {
                Util::RecordReader reader(a_intfc, length);
                const auto load = [&](Registrations& entries) {
                    const auto count = reader.Count(16);
                    for (uint64_t i = 0; i < count; ++i) {
                        const auto id = reader.Read<uint32_t>();
                        const auto countEvents = reader.Count(9);
                        std::vector<RE::BSFixedString> callbacks;
                        callbacks.reserve(static_cast<size_t>(countEvents));
                        for (uint64_t n = 0; n < countEvents; ++n) callbacks.emplace_back(reader.String());
                        if (reader.Read<uint32_t>() != UINT32_MAX)
                            throw std::runtime_error("Invalid tracking entry delimiter");
                        RE::FormID resolved;
                        if (a_intfc->ResolveFormID(id, resolved))
                            entries.insert_or_assign(resolved, std::move(callbacks));
                    }
                };
                load(factions);
                load(actors);
                if (reader.Remaining())
                    throw std::runtime_error("Unexpected trailing tracking data");
            } catch (const std::exception& error) {
                logger::error("Tracking record rejected: {}", error.what());
                factions.clear();
                actors.clear();
            }
            std::unique_lock lock{ _mutex };
            _factions = std::move(factions);
            _actors = std::move(actors);
        }

        void Revert(SKSE::SerializationInterface*)
        {
            std::unique_lock lock{ _mutex };
            _factions.clear();
            _actors.clear();
        }
    };
}
