#include "Settings.h"
#include "SettingsValidation.h"
#include "Util/SaveQueue.h"

#include <SimpleIni.h>

void Settings::Initialize()
{
    InitializeYAML();
    InitializeINI();
    InitializeData();
}

template <typename T>
struct is_vector : std::false_type
{};

template <typename T, typename Alloc>
struct is_vector<std::vector<T, Alloc>> : std::true_type
{};

void Settings::InitializeYAML()
{
    if (!fs::exists(YAMLPATH)) {
        logger::error("No Settings file (yaml) in {}", YAMLPATH);
        return;
    }

    try {
        const auto yaml = YAML::LoadFile(YAMLPATH);
        const auto ReadMCM = [&yaml]<typename T>(const char* a_key, T& a_out) {
            if (!yaml[a_key].IsDefined())
                return;
            const auto val = yaml[a_key].as<T>();
            if constexpr (is_vector<std::decay_t<T>>::value) {
                if (a_out.size() != val.size()) {
                    logger::error("Invalid array length for setting {}, expected {} but got {}", a_key, a_out.size(), val.size());
                    return;
                }
            }
            if (!SettingsValidation::IsValid(a_key, val)) {
                logger::warn("Invalid setting {}; keeping current value", a_key);
                return;
            }
            a_out = val;
        };
#define MCM_SETTING(STR, DEFAULT) ReadMCM(#STR, STR);
#include "mcm.def"
#undef MCM_SETTING

        logger::info("Finished loading yaml settings");
    } catch (const std::exception& e) {
        logger::error("Unable to laod settings, error: {}", e.what());
    }
}

void Settings::InitializeINI()
{
    if (!fs::exists(INIPATH)) {
        logger::error("No Settings file (ini) in {}", INIPATH);
        return;
    }
    CSimpleIniA inifile{};
    inifile.SetUnicode();
    const auto ec = inifile.LoadFile(INIPATH);
    if (ec < 0) {
        logger::error("Failed to read .ini Settings, Error: {}", ec);
        return;
    }
    const auto ReadIni = [&inifile]<typename T>(const char* a_section, const char* a_option, T& a_out) {
        if (!inifile.GetValue(a_section, a_option))
            return;
        if constexpr (std::is_integral_v<T>) {
            a_out = static_cast<T>(inifile.GetLongValue(a_section, a_option));
        } else if constexpr (std::is_floating_point_v<T>) {
            const auto value = static_cast<T>(inifile.GetDoubleValue(a_section, a_option));
            // Percentage normalization below already handles invalid values
            // and uses double precision for arbitrarily large finite totals.
            if (std::string_view(a_option) == "fPercentageHetero" ||
                std::string_view(a_option) == "fPercentageHomo" ||
                SettingsValidation::IsValid(a_option, value))
                a_out = value;
            else
                logger::warn("Invalid setting {}; keeping current value", a_option);
        } else {
            logger::error("Unknown Type for option {} in section {}", a_option, a_section);
        }
    };
#define INI_SETTING(STR, DEFAULT, CAT) ReadIni(CAT, #STR, STR);
#include "config.def"
#undef INI_SETTING

    if (!std::isfinite(fFurnitureSquare) || fFurnitureSquare < 0.0f) {
        logger::warn("Invalid fFurnitureSquare {}; using default", fFurnitureSquare);
        fFurnitureSquare = 32.0f;
    }
    if (!std::isfinite(fFurnitureSquareStepSize) || fFurnitureSquareStepSize < 1.0f) {
        logger::warn("Invalid fFurnitureSquareStepSize {}; using default", fFurnitureSquareStepSize);
        fFurnitureSquareStepSize = 8.0f;
    }

    if (!std::isfinite(fPercentageHetero) || fPercentageHetero < 0.0f) {
        logger::warn("Invalid fPercentageHetero {}; using default", fPercentageHetero);
        fPercentageHetero = 80.0f;
    }
    if (!std::isfinite(fPercentageHomo) || fPercentageHomo < 0.0f) {
        logger::warn("Invalid fPercentageHomo {}; using default", fPercentageHomo);
        fPercentageHomo = 9.0f;
    }
    const auto total = double(fPercentageHetero) + double(fPercentageHomo);
    if (total > 100.0) {
        logger::error("Sexuality Percentage Settings must be at most 100.0");
        fPercentageHetero = static_cast<float>((double(fPercentageHetero) / total) * 100.0);
        fPercentageHomo = static_cast<float>((double(fPercentageHomo) / total) * 100.0);
        // Rounding both percentages upward must not invert the remaining range.
        fPercentageHomo = std::min(fPercentageHomo, 100.0f - fPercentageHetero);
        logger::info("Adjusted fPercentageHetero to {} and fPercentageHomo to {}", fPercentageHetero, fPercentageHomo);
    }
    logger::info("Finished loading .ini settings");
}

void Settings::InitializeData()
{
    try {
        const auto& handler = RE::TESDataHandler::GetSingleton();
        const auto root = YAML::LoadFile(SCHLONGPATH);
        SOS_ExcludeFactions.clear();
        for (auto&& i : root["Blacklist"]) {
            const auto esp = i["ESP"].as<std::string>();
            logger::info("Looking for non-schlongs in esp {}", esp);
            const auto node = i["ID"];
            if (node.IsSequence()) {
                for (auto&& id : node) {
                    const auto formid = id.as<uint32_t>();
                    const auto fac = handler->LookupFormID(formid, esp);
                    if (fac) {
                        logger::info("Adding {} / {}", esp, formid);
                        SOS_ExcludeFactions.push_back(fac);
                    }
                }
            } else {  // no sequence, simple entry
                const auto formid = node.as<uint32_t>();
                const auto fac = handler->LookupFormID(formid, esp);
                if (fac) {
                    logger::info("Adding {} / {}", esp, formid);
                    SOS_ExcludeFactions.push_back(fac);
                }
            }
        }
    } catch (const std::exception& e) {
        logger::error("Unable to load {}: {}", SCHLONGPATH, e.what());
    }
}

void Settings::Save()
{
    try {
        YAML::Node settings{};
        {
            std::scoped_lock lock{ saveMutex };
#define MCM_SETTING(STR, DEFAULT) settings[#STR] = STR;
#include "mcm.def"
#undef MCM_SETTING
        }
        Util::SaveQueue::Get().Submit(YAMLPATH, YAML::Dump(settings));
    } catch (const std::exception& e) {
        logger::error("Unable to snapshot settings: {}", e.what());
    }
}

Settings::KeyType Settings::GetKeyType(uint32_t a_keyCode)
{
    const auto get = [](uint32_t key) {
        return key >= SKSE::InputMap::kMacro_GamepadOffset ? SKSE::InputMap::GamepadKeycodeToMask(key) : key;
    };
    if (a_keyCode == get(Settings::iToggleSceneHUD))
        return KeyType::Menu;
    if (a_keyCode == get(Settings::iFocusSceneHUD))
        return KeyType::Focus;
    if (a_keyCode == get(Settings::iKeyAdvance))
        return KeyType::Advance;
    if (a_keyCode == get(Settings::iKeyEnd))
        return KeyType::End;
    if (a_keyCode == get(Settings::iKeyMod))
        return KeyType::Modifier;
    if (a_keyCode == get(Settings::iChangeAnimation))
        return KeyType::Scene;
    if (a_keyCode == get(Settings::iMoveScene))
        return KeyType::Move;
    if (a_keyCode == get(Settings::iToggleSceneGraph))
        return KeyType::Graph;
    if (a_keyCode == get(Settings::iToggleThreadControl))
        return KeyType::Thread;
    if (a_keyCode == get(Settings::iToggleFreeCamera))
        return KeyType::FreeCam;
    if (a_keyCode == get(Settings::iTargetActor))
        return KeyType::Partner;
    if (a_keyCode == get(Settings::iGameRaiseEnjKey))
        return KeyType::RaiseEnj;
    if (a_keyCode == get(Settings::iGameHoldbackKey))
        return KeyType::Holdback;
    return KeyType::None;
}

uint32_t Settings::GetKeyCode(KeyType a_keyType)
{
    const auto get = [](uint32_t key) {
        return key >= SKSE::InputMap::kMacro_GamepadOffset ? SKSE::InputMap::GamepadKeycodeToMask(key) : key;
    };
    switch (a_keyType) {
    case KeyType::Menu:
        return get(Settings::iToggleSceneHUD);
    case KeyType::Focus:
        return get(Settings::iFocusSceneHUD);
    case KeyType::Advance:
        return get(Settings::iKeyAdvance);
    case KeyType::End:
        return get(Settings::iKeyEnd);
    case KeyType::Modifier:
        return get(Settings::iKeyMod);
    case KeyType::Scene:
        return get(Settings::iChangeAnimation);
    case KeyType::Move:
        return get(Settings::iMoveScene);
    case KeyType::Graph:
        return get(Settings::iToggleSceneGraph);
    case KeyType::Thread:
        return get(Settings::iToggleThreadControl);
    case KeyType::FreeCam:
        return get(Settings::iToggleFreeCamera);
    case KeyType::Partner:
        return get(Settings::iTargetActor);
    case KeyType::RaiseEnj:
        return get(Settings::iGameRaiseEnjKey);
    case KeyType::Holdback:
        return get(Settings::iGameHoldbackKey);
    default:
        logger::warn("GetKeyCode: Invalid KeyType {}", static_cast<int>(a_keyType));
        return 0;  // Return 0 for KeyType::None or invalid KeyType
    }
}
