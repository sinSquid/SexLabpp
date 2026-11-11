#pragma once

#include <atomic>
#include <mutex>
#include <type_traits>

template <typename T, bool = std::is_arithmetic_v<T>>
struct SettingStorage
{
    using Type = T;
};

template <typename T>
struct SettingStorage<T, true>
{
    using Type = std::atomic<T>;
};

struct StringCmp
{
    bool operator()(const std::string& a_lhs, const std::string& a_rhs) const { return _strcmpi(a_lhs.c_str(), a_rhs.c_str()) < 0; }
};

struct Settings
{
    static void Initialize();
    static void Save();
    // Compound values use this lock; scalar MCM fields are atomic for direct readers.
    static std::unique_lock<std::mutex> Lock() { return std::unique_lock{ _mutex }; }
    template <typename T>
    using Storage = typename SettingStorage<T>::Type;
    template <typename T>
    static T Read(const std::atomic<T>& a_value) { return a_value.load(std::memory_order_relaxed); }
    template <typename T>
    static T Read(const T& a_value) { return a_value; }  // Compound caller holds Lock().

    // --- Key Codes
    enum class KeyType
    {
        None,
        Menu,
        Focus,
        Advance,
        End,
        Modifier,
        Scene,
        Move,
        Graph,
        Position,
        Thread,
        FreeCam,
        Partner,
        RaiseEnj,
        Holdback,
    };
    static KeyType GetKeyType(uint32_t a_keyCode);
    static uint32_t GetKeyCode(KeyType a_keyType);

    // --- MCM
    enum class FurnitureSlection
    {
        Never = 0,
        Sometimes = 1,
        Always = 2,
        AskAlways = 3,
        IfNotSubmissive = 4,
    };

#define MCM_SETTING(STR, DEFAULT) static inline Storage<decltype(DEFAULT)> STR{ DEFAULT };
#include "mcm.def"
#undef MCM_SETTING

    using SettingsVariants = std::variant<std::atomic<float>*, std::string*, std::atomic<bool>*, std::atomic<int>*, std::vector<float>*, std::vector<int>*>;
    static inline std::map<std::string, SettingsVariants, StringCmp> table{
#define MCM_SETTING(STR, DEFAULT) { #STR##s, &STR },
#include "mcm.def"
#undef MCM_SETTING
    };

    // --- INI
#define INI_SETTING(STR, DEFAULT, CAT) static inline decltype(DEFAULT) STR{ DEFAULT };
#include "config.def"
#undef INI_SETTING

    // --- Misc
    static inline std::vector<RE::FormID> SOS_ExcludeFactions{};

  private:
    static inline std::mutex _mutex;
    static void InitializeYAML();
    static void InitializeINI();
    static void InitializeData();
};
