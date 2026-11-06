#pragma once

#include "Papyrus/sslLibrary/Serialize.h"
#include "Registry/Stats.h"
#include "Thread/Collision/CollisionHandler.h"

namespace Serialization
{
    inline std::string GetTypeName(uint32_t a_type)
    {
        constexpr auto size = sizeof(uint32_t);
        std::string ret{};
        ret.resize(size);
        const char* it = reinterpret_cast<char*>(&a_type);
        for (size_t i = 0, j = size - 1; i < size; i++, j--)
            ret[j] = std::isprint(it[i]) ? it[i] : '_';

        return ret;
    }

    class Serialize final :
      public Singleton<Serialize>
    {
      public:
        enum : std::uint32_t
        {
            _Version = 1,
            _StatisticsVersion = 2,

            _Statistics = 'stcs',
            _Tracking = 'trcn'
        };

        static void SaveCallback(SKSE::SerializationInterface* a_intfc)
        {
#define SAVE(type, version, func)                          \
    if (!a_intfc->OpenRecord(type, version)) {              \
        std::string insert = #type##s;                     \
        logger::error("Failed to open record {}", insert); \
    } else {                                               \
        func;                                              \
    }
            SAVE(_Statistics, _StatisticsVersion, Registry::Statistics::StatisticsData::GetSingleton()->Save(a_intfc))
            SAVE(_Tracking, _Version, Papyrus::Tracking::GetSingleton()->Save(a_intfc))

#undef SAVE
        }

        static void LoadCallback(SKSE::SerializationInterface* a_intfc)
        {
            uint32_t type, version, length;
            while (a_intfc->GetNextRecordInfo(type, version, length)) {
                logger::info("Loading record {}", GetTypeName(type));
                switch (type) {
                case _Statistics:
                    if (version == _Version || version == _StatisticsVersion) {
                        Registry::Statistics::StatisticsData::GetSingleton()->Load(a_intfc, version, length);
                    } else {
                        logger::warn("Unsupported statistics record version: {}", version);
                    }
                    break;
                case _Tracking:
                    if (version == _Version) {
                        Papyrus::Tracking::GetSingleton()->Load(a_intfc);
                    } else {
                        logger::warn("Unsupported tracking record version: {}", version);
                    }
                    break;
                default:
                    break;
                }
            }

            logger::info("Finished loading data from cosave");
        }

        static void RevertCallback(SKSE::SerializationInterface* a_intfc)
        {
            Thread::Collision::CollisionHandler::Clear();
            Registry::Statistics::StatisticsData::GetSingleton()->Revert(a_intfc);
            Papyrus::Tracking::GetSingleton()->Revert(a_intfc);
        }

        static void FormDeleteCallback(RE::VMHandle)
        {
        }

    };  // class Serialize

}  // namespace Serialization
