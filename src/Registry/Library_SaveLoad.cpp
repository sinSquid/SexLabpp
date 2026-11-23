#include "Library.h"

#include "SceneIndexPublication.h"
#include "Util/Combinatorics.h"
#include "Util/StringUtil.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#include <atomic>
#include <fstream>
#include <system_error>
#include <thread>
#include <unordered_set>
#include <utility>

namespace Registry
{
    namespace
    {
        template <class Job>
        void QueueRegistryJob(std::vector<std::jthread>& a_workers, const Job& a_job)
        {
            try {
                a_workers.emplace_back(a_job);
            } catch (const std::system_error& e) {
                logger::warn("Could not start a registry worker, running its job inline: {}", e.what());
                a_job();
            }
        }

        template <class Job>
        void RunRegistryJob(const char* a_description, const Job& a_job)
        {
            try {
                a_job();
            } catch (const std::exception& e) {
                logger::error("{}: {}", a_description, e.what());
            } catch (...) {
                logger::error("{}: unknown exception", a_description);
            }
        }

        fs::path MakeSceneSettingsPath(const fs::path& a_directory, std::string_view a_filename)
        {
            const fs::path filename{ a_filename };
            const auto& nativeName = filename.native();
            if (nativeName.empty() || nativeName == L"." || nativeName == L".." ||
                nativeName.find_first_of(LR"(\/:*?"<>|)") != std::wstring::npos ||
                std::ranges::any_of(nativeName, [](wchar_t c) { return c < 32; })) {
                throw std::invalid_argument("Invalid scene settings filename");
            }
            return a_directory / filename;
        }

        fs::path RegistryIOPath(const fs::path& a_path)
        {
            const auto& input = a_path.native();
            if (input.starts_with(LR"(\\?\)") || input.starts_with(LR"(\\.\)")) {
                return a_path;
            }
            auto absolute = fs::absolute(a_path).lexically_normal();
            absolute.make_preferred();
            const auto& native = absolute.native();
            if (native.size() < MAX_PATH) {
                return a_path;
            }
            if (native.starts_with(LR"(\\)")) {
                return fs::path{ LR"(\\?\UNC\)" + native.substr(2) };
            }
            return fs::path{ LR"(\\?\)" + native };
        }

        std::string RegistryPathLabel(const fs::path& a_path)
        {
            const auto utf8 = a_path.u8string();
            return { reinterpret_cast<const char*>(utf8.data()), utf8.size() };
        }

        std::optional<YAML::Node> ReadRegistryYaml(const fs::path& a_path, bool a_validateEntireFile = false)
        {
            const auto path = RegistryIOPath(a_path);
            const auto status = fs::symlink_status(path);
            if (status.type() == fs::file_type::not_found) {
                return std::nullopt;
            }
            if (!fs::is_regular_file(status) && (!fs::is_symlink(status) || !fs::is_regular_file(path))) {
                throw std::runtime_error("Expected a regular registry file");
            }

            std::ifstream input(path, std::ios::binary);
            if (!input.is_open()) {
                throw std::runtime_error("Could not open registry file for reading");
            }
            input.exceptions(std::ios::badbit);
            YAML::Node root;
            if (a_validateEntireFile) {
                // The emitter writes one document. Refuse to replace a file with unread or extra content.
                const auto documents = YAML::LoadAll(input);
                if (documents.size() > 1) {
                    throw std::runtime_error("Expected one registry YAML document");
                }
                if (!documents.empty()) {
                    root = documents.front();
                }
            } else {
                root = YAML::Load(input);
            }
            if (input.fail() && !input.eof()) {
                throw std::runtime_error("Could not read registry file");
            }
            if (!root.IsNull() && !root.IsMap()) {
                throw std::runtime_error("Expected a registry YAML mapping");
            }
            return root;
        }

        bool SaveRegistryYaml(const fs::path& a_path, const YAML::Node& a_data)
        {
            static std::atomic_uint64_t nextTemporaryFile{ 0 };
            fs::path temporary;
            bool ownsTemporary = false;
            try {
                const auto destination = RegistryIOPath(a_path);
                const auto name = std::format(L".slpp-{}-{}.tmp", ::GetCurrentProcessId(), nextTemporaryFile.fetch_add(1, std::memory_order_relaxed));
                temporary = RegistryIOPath(destination.parent_path() / name);
                fs::create_directories(temporary.parent_path());
                std::ofstream output(temporary, std::ios::noreplace);
                if (!output.is_open())
                    throw std::runtime_error("Could not create temporary file");
                ownsTemporary = true;
                {
                    YAML::Emitter yaml(output);
                    yaml << a_data;
                    if (!yaml.good())
                        throw std::runtime_error(yaml.GetLastError());
                }
                output.close();
                if (!output)
                    throw std::runtime_error("Could not write or close temporary file");
                if (!::MoveFileExW(temporary.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING))
                    throw std::system_error(static_cast<int>(::GetLastError()), std::system_category(), "Could not replace destination");
                return true;
            } catch (const std::exception& e) {
                logger::error("Failed to save {}: {}", RegistryPathLabel(a_path), e.what());
                if (ownsTemporary) {
                    std::error_code error;
                    fs::remove(temporary, error);
                    if (error)
                        logger::warn("Could not remove temporary file {}: {}", RegistryPathLabel(temporary), error.message());
                }
                return false;
            }
        }
    }

    struct CumFxTextureSource
    {
        std::string type;
        std::string path;
    };

    struct CumFxConfigSource
    {
        std::optional<int32_t> priority;
        std::optional<std::vector<std::string>> races;
        std::optional<std::vector<CumFxTextureSource>> textures;
    };

    void Library::Initialize() noexcept
    {
        logger::info("Loading Library");
        const auto tStart = std::chrono::high_resolution_clock::now();
#ifndef SKYRIMVR
        std::vector<std::jthread> threads;
#endif
        const auto initialize = [&](const char* description, auto loader) {
            const auto job = [this, description, loader]() {
                RunRegistryJob(description, [&]() { (this->*loader)(); });
            };
#ifndef SKYRIMVR
            QueueRegistryJob(threads, job);
#else
            job();
#endif
        };
        initialize("Failed to initialize scenes", &Library::InitializeScenes);
        initialize("Failed to initialize voices", &Library::InitializeVoice);
        initialize("Failed to initialize expressions", &Library::InitializeExpressions);
        initialize("Failed to initialize furniture", &Library::InitializeFurnitures);
        initialize("Failed to initialize CumFx", &Library::InitializeCumFx);
#ifndef SKYRIMVR
        for (auto& thread : threads) {
            thread.join();
        }
#endif

        const auto tEnd = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double, std::milli> ms = tEnd - tStart;
        logger::info("Loaded {} Packages ({} scenes | {} categories)", packages.size(), GetSceneCount(), scenes.size());
        logger::info("Loaded {} Voices", voices.size());
        logger::info("Loaded {} VoiceType-Pitches", savedPitches.size());
        logger::info("Loaded {} Cached Voices", savedVoices.size());
        logger::info("Loaded {} Expressions", expressions.size());
        logger::info("Loaded {} CumFx Profiles", std::accumulate(fxList.begin(), fxList.end(), 0ull, [](auto acc, const auto& config) {
            return acc + std::accumulate(config.profiles.begin(), config.profiles.end(), 0ull, [](auto count, const auto& profiles) { return count + profiles.size(); });
        }));
        logger::info("Loaded {} Furnitures", furnitures.size());
        logger::info("Library loaded in {}ms", ms.count());
    }

    bool Library::FolderExists(const char* path, bool notifyUser) const
    {
        std::error_code ec{};
        if (!fs::exists(path, ec) || fs::is_empty(path, ec)) {
            const auto msg = ec ? std::format("An error occured while initializing {}: {}", path, ec.message()) :
                                  std::format("Unable to open {}. Folder is empty or does not exist.", path);
            if (notifyUser) {
                logger::critical("{}", msg);
                const auto msgBox = std::format("{}\n\nExit game now?", msg);
                if (REX::W32::MessageBoxA(nullptr, msgBox.c_str(), "SexLab p+ Registry", 0x00000004) == 6) {
                    std::_Exit(EXIT_FAILURE);
                }
            } else {
                logger::warn("{}", msg);
            }
            return false;
        }
        return true;
    }

    void Library::InitializeScenes()
    {
        if (!FolderExists(SCENE_PATH, true))
            return;
#ifndef SKYRIMVR
        std::vector<std::jthread> threads;
#endif
        for (auto& file : fs::recursive_directory_iterator{ SCENE_PATH }) {
            if (file.path().extension() != ".slr")
                continue;
            const auto load = [this, file]() {
                std::string filename;
                try {
                    filename = file.path().filename().string();
                    auto package = std::make_unique<AnimPackage>(file);
                    std::vector<std::unordered_set<ActorFragment::FragmentHash>> sceneKeys(package->scenes.size());
                    for (std::size_t i = 0; i < package->scenes.size(); ++i) {
                        const auto& scene = package->scenes[i];
                        std::vector<std::vector<ActorFragment>> positionFragments;
                        positionFragments.reserve(scene->positions.size());
                        for (const auto& position : scene->positions)
                            positionFragments.push_back(position.data.Split());
                        Combinatorics::ForEachCombination<ActorFragment>(positionFragments, [&](const std::vector<std::vector<ActorFragment>::const_iterator>& it) {
                            std::vector<ActorFragment> argFragment{};
                            argFragment.reserve(it.size());
                            for (auto&& itF : it) {
                                argFragment.emplace_back(*itF);
                            }
                            sceneKeys[i].insert(ActorFragment::MakeFragmentHash(std::move(argFragment)));
                            return Combinatorics::CResult::Next;
                        });
                    }
                    {
                        const std::unique_lock lock{ _mScenes };
                        PublishScenePackage(std::move(package), sceneKeys, packages, scenes, sceneMap, scenePackages);
                    }
                    logger::info("InitializeScenes: Finished parsing file {}", filename);
                } catch (const std::exception& e) {
                    logger::error("InitializeScenes: Failed to load {}: {}", filename, e.what());
                } catch (...) {
                    logger::error("InitializeScenes: Failed to load {} due to an unknown exception", filename);
                }
            };
#ifndef SKYRIMVR
            QueueRegistryJob(threads, load);
#else
            load();
#endif
        }
#ifndef SKYRIMVR
        for (auto& thread : threads) {
            thread.join();
        }
#endif
        InitializeSceneSettings();
    }

    void Library::InitializeSceneSettings()
    {
        const auto directory = RegistryIOPath(SCENE_USER_CONFIG);
        if (!fs::exists(directory))
            return;
        std::unique_lock lock{ _mScenes };
        for (const auto& file : fs::directory_iterator{ directory }) {
            if (const auto ext = file.path().extension(); ext != ".yaml" && ext != ".yml")
                continue;
            const auto filename = RegistryPathLabel(file.path().filename());
            try {
                const auto root = ReadRegistryYaml(file.path());
                if (!root)
                    continue;
                for (auto&& [key, scene] : sceneMap) {
                    const auto node = (*root)[scene->id];
                    if (!node.IsDefined())
                        continue;
                    scene->Load(node);
                }
                logger::info("InitializeScenes: Finished parsing file {}", filename);
            } catch (const std::exception& e) {
                logger::error("InitializeScenes: Failed to load {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeFurnitures()
    {
        if (!FolderExists(FURNITURE_PATH, false))
            return;
        const std::unique_lock lock{ _mFurniture };
        for (auto& file : fs::recursive_directory_iterator{ FURNITURE_PATH }) {
            if (auto ext = file.path().extension(); ext != ".yml" && ext != ".yaml") {
                continue;
            }
            const auto filename = file.path().filename().string();
            try {
                YAML::Node root = YAML::LoadFile(file.path().string());
                for (auto&& it : root) {
                    furnitures.emplace(
                        RE::BSFixedString(it.first.as<std::string>()),
                        std::make_unique<FurnitureDetails>(it.second));
                }
                logger::info("RegisterFurniture: Finished parsing file {}", filename);
            } catch (const std::exception& e) {
                logger::error("RegisterFurniture: Failed to load {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeExpressions()
    {
        std::unique_lock lock{ _mExpressions };
        // NOTE: Intialization happens in stages, beginning with default (P+) expressions, then legacy & default.
        // This is to ensure that default expressions are always available, even if the user has not installed any custom expressions yet.
        // Further if the user has installed legacy expressions, they will be converted to the new format iff they have not been converted already.
        InitializeExpressionsImpl();
        InitializeExpressionsLegacy();
        constexpr auto arr = magic_enum::enum_entries<Expression::DefaultExpression>();
        for (auto&& [value, name] : arr) {
            if (expressions.contains(name)) {
                continue;
            }
            expressions.emplace(name, Expression{ value });
            logger::info("InitializeExpressions: Added default expression {}", name);
        }
    }

    void Library::InitializeExpressionsImpl()
    {
        if (!FolderExists(EXPRESSION_PATH, false))
            return;
        for (auto& file : fs::recursive_directory_iterator{ EXPRESSION_PATH }) {
            const auto extension = file.path().extension();
            if (extension != ".yaml" && extension != ".yml")
                continue;
            const auto filename = file.path().filename().string();
            try {
                const auto yaml = YAML::LoadFile(file.path().string());
                auto profile = Expression{ yaml };
                if (expressions.emplace(profile.GetId(), std::move(profile)).second) {
                    logger::info("InitializeExpressions: Added expression {}", filename);
                } else {
                    logger::warn("InitializeExpressions: Expression {} already exists, skipping", filename);
                }
            } catch (const std::exception& e) {
                logger::error("InitializeExpressions: Failed to load {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeExpressionsLegacy()
    {
        if (!FolderExists(EXPRESSION_LEGACY_CONFIG, false))
            return;
        for (auto& file : fs::directory_iterator{ EXPRESSION_LEGACY_CONFIG }) {
            auto filename = file.path().filename().string();
            Util::ToLower(filename);
            if (!filename.starts_with("expression"))
                continue;
            try {
                auto profile = Expression::FromLegacyFile(file.path());
                auto succ = expressions.emplace(profile.GetId(), std::move(profile));
                if (succ.second) {
                    succ.first->second.Save(EXPRESSION_PATH, true);
                    logger::info("InitializeExpressions: Added legacy expression {}. This file may now be deleted", filename);
                }
            } catch (const std::exception& e) {
                logger::error("InitializeExpressions: Failed to load {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeVoice()
    {
        std::unique_lock lock{ _mVoice };
        InitializeVoiceImpl();
        InitializeVoicePitches();
        InitializeVoiceSettings();
        InitializeVoiceCache();
    }

    void Library::InitializeVoiceImpl()
    {
        if (!FolderExists(VOICE_PATH, true))
            return;
        for (auto& file : fs::recursive_directory_iterator{ VOICE_PATH }) {
            if (const auto ext = file.path().extension(); ext != ".yaml" && ext != ".yml")
                continue;
            const auto filename = file.path().filename().string();
            try {
                const auto root = YAML::LoadFile(file.path().string());
                auto voice = Voice{ root };
                if (voices.emplace(voice.GetId(), std::move(voice)).second) {
                    logger::info("InitializeVoice: Added voice {}", filename);
                } else {
                    logger::warn("InitializeVoice: Voice {} already exists, skipping", filename);
                }
            } catch (const std::exception& e) {
                logger::error("InitializeVoice: Error while loading scene settings from file {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeVoicePitches()
    {
        if (!FolderExists(VOICE_PATH_PITCH, false))
            return;
        for (auto& file : fs::recursive_directory_iterator{ VOICE_PATH_PITCH }) {
            if (const auto ext = file.path().extension(); ext != ".yaml" && ext != ".yml")
                continue;
            const auto filename = file.path().filename().string();
            try {
                const auto root = YAML::LoadFile(file.path().string());
                for (auto&& it : root) {
                    auto formIdStr = it.first.as<std::string>();
                    auto id = Util::FormFromString(formIdStr);
                    if (id == 0) {
                        logger::error("InitializeVoicePitches: Invalid form ID: {} in file {}", formIdStr, filename);
                        continue;
                    }
                    const auto pitchStr = it.second.as<std::string>();
                    auto pitch = magic_enum::enum_cast<Pitch>(pitchStr);
                    if (!pitch.has_value()) {
                        auto voice = voices.find(pitchStr);
                        if (voice == voices.end()) {
                            logger::error("InitializeVoicePitches: Unknown Pitch {} in file {}", pitchStr, filename);
                            continue;
                        }
                        savedPitches.insert_or_assign(id, &voice->second);
                    } else {
                        savedPitches.insert_or_assign(id, pitch.value());
                    }
                }
                logger::info("InitializeVoicePitches: Finished parsing file {}", filename);
            } catch (const std::exception& e) {
                logger::error("InitializeVoicePitches: Error while loading voice pitches from file {}: {}", filename, e.what());
            }
        }
    }

    void Library::InitializeVoiceSettings()
    {
        try {
            const auto root = ReadRegistryYaml(VOICE_SETTING_PATH);
            if (!root)
                return;
            for (auto&& it : *root) {
                RunRegistryJob("Failed to load a voice setting", [&]() {
                    const RE::BSFixedString voiceId = it.first.as<std::string>();
                    const auto voice = voices.find(voiceId);
                    if (voice == voices.end()) {
                        logger::error("InitializeVoice: Unknown voice {} in settings file", voiceId);
                        return;
                    }
                    voice->second.Load(it.second);
                });
            }
            logger::info("InitializeVoice: Loaded Voice Settings");
        } catch (const std::exception& e) {
            logger::error("InitializeVoice: Error while loading voice settings: {}", e.what());
        }
    }

    void Library::InitializeVoiceCache()
    {
        try {
            const auto root = ReadRegistryYaml(VOICE_SETTINGS_CACHES_PATH);
            if (!root)
                return;
            for (auto&& it : *root) {
                RunRegistryJob("Failed to load a cached voice assignment", [&]() {
                    const auto npcIdStr = it.first.as<std::string>();
                    const auto id = Util::FormFromString(npcIdStr);
                    if (id == 0)
                        return;
                    const auto voiceStr = it.second.as<std::string>();
                    const auto voice = voices.find(voiceStr);
                    if (voice == voices.end()) {
                        logger::error("InitializeVoice: Actor {:X} uses unknown Voice {}", id, voiceStr);
                        return;
                    }
                    const auto& v = voice->second;
                    savedVoices.insert_or_assign(id, &v);
                });
            }
        } catch (const std::exception& e) {
            logger::error("InitializeVoice: Error while loading cached voices: {}", e.what());
        }
    }

    void Library::InitializeCumFx()
    {
        fxList.clear();
        if (!FolderExists(CUM_FX_CONFIG_PATH, true))
            return;
        try {
            for (const auto& file : fs::directory_iterator{ CUM_FX_CONFIG_PATH }) {
                if (!file.is_regular_file() || file.path().extension() != ".json") {
                    continue;
                }
                const auto filename = file.path().filename().string();
                CumFxConfigSource source;
                std::string buffer;
                if (const auto error = glz::read_file_json(source, file.path().string(), buffer); error) {
                    logger::error("Unable to load CumFx config {}: {}", filename, glz::format_error(error, buffer));
                    continue;
                }
                if (!source.priority || !source.races || !source.textures || source.textures->empty()) {
                    logger::error("CumFx config {} must define priority, races, and at least one texture", filename);
                    continue;
                }

                FxConfig config{ .priority = *source.priority };
                bool valid = true;
                for (const auto& raceId : *source.races) {
                    const auto race = Util::FormFromString<RE::TESRace>(raceId);
                    if (!race) {
                        logger::error("CumFx config {} has invalid race {}", filename, raceId);
                        valid = false;
                        break;
                    }
                    config.races.push_back(race);
                }
                if (!valid) {
                    continue;
                }

                for (const auto& texture : *source.textures) {
                    const auto type = magic_enum::enum_cast<FxType>(texture.type, magic_enum::case_insensitive);
                    if (!type) {
                        logger::error("CumFx config {} has invalid type {}", filename, texture.type);
                        valid = false;
                        break;
                    }
                    auto pathString = texture.path;
                    std::ranges::replace(pathString, '\\', '/');
                    const fs::path relativePath{ pathString };
                    const auto normalizedPath = relativePath.lexically_normal();
                    const auto normalizedString = normalizedPath.generic_string();
                    if (relativePath.empty() || relativePath.is_absolute() || normalizedString == ".." || normalizedString.starts_with("../")) {
                        logger::error("CumFx config {} has invalid path {}", filename, texture.path);
                        valid = false;
                        break;
                    }
                    const auto profilePath = fs::path{ CUM_FX_PATH } / normalizedPath;
                    if (!fs::exists(profilePath) || !fs::is_directory(profilePath)) {
                        logger::error("CumFx config {} profile path does not exist: {}", filename, profilePath.string());
                        valid = false;
                        break;
                    }
                    const auto layerCount = InitializeCumFxType(profilePath);
                    if (layerCount == 0) {
                        logger::error("CumFx config {} has invalid profile: {}", filename, profilePath.string());
                        valid = false;
                        break;
                    }
                    config.profiles[static_cast<size_t>(*type)].push_back({ RE::BSFixedString{ normalizedPath.generic_string() }, layerCount });
                }
                if (valid) {
                    logger::info("Loaded CumFx config: {}", filename);
                    fxList.push_back(std::move(config));
                }
            }
        } catch (const std::exception& e) {
            logger::error("Unable to initialize CumFx configs: {}", e.what());
        }
        if (fxList.empty()) {
            logger::error("No valid CumFx configs found");
        }
    }

    uint8_t Library::InitializeCumFxType(const fs::path& a_typePath) const
    {
        std::vector<uint8_t> fxFiles;
        std::vector<uint8_t> normalFiles;
        for (const auto& file : fs::directory_iterator(a_typePath)) {
            if (!file.is_regular_file() || file.path().extension() != ".dds") {
                logger::warn("Invalid file type: {}. Expected .dds", file.path().string());
                continue;
            }
            auto numberPart = file.path().stem().string();
            const bool isNormalMap = numberPart.ends_with("_n");
            if (isNormalMap) {
                numberPart.resize(numberPart.size() - 2);
            }
            uint32_t number = 0;
            const auto [end, error] = std::from_chars(numberPart.data(), numberPart.data() + numberPart.size(), number);
            if (error != std::errc{} || end != numberPart.data() + numberPart.size() || number == 0 || number > std::numeric_limits<uint8_t>::max() || numberPart != std::to_string(number)) {
                logger::warn("Invalid CumFx file name: {}", file.path().string());
                continue;
            }
            (isNormalMap ? normalFiles : fxFiles).push_back(static_cast<uint8_t>(number));
        }
        if (fxFiles.empty()) {
            logger::error("No valid files found in directory: {}", a_typePath.string());
            return 0;
        }
        std::sort(fxFiles.begin(), fxFiles.end());
        if (fxFiles.front() != 1) {
            logger::error("First file number is not 1 in directory: {}", a_typePath.string());
            return 0;
        }
        uint8_t expectedFileNumber = 1;
        for (const auto fileNumber : fxFiles) {
            if (fileNumber != expectedFileNumber) {
                logger::error("Missing file number {} in directory: {}", expectedFileNumber, a_typePath.string());
                return 0;
            }
            ++expectedFileNumber;
        }
        for (const auto fileNumber : normalFiles) {
            if (!std::ranges::contains(fxFiles, fileNumber)) {
                logger::warn("Normal map {}_n.dds has no matching diffuse texture in directory: {}", fileNumber, a_typePath.string());
            }
        }
        return static_cast<uint8_t>(fxFiles.size());
    }

    void Library::Save() const noexcept
    {
        bool scenesSaved = false;
        RunRegistryJob("Failed to save scene settings", [&]() { scenesSaved = SaveScenes(); });
        SaveExpressions();
        bool voicesSaved = false;
        RunRegistryJob("Failed to save voice settings", [&]() { voicesSaved = SaveVoices(); });
        if (scenesSaved && voicesSaved) {
            logger::info("Finished saving registry settings");
        } else {
            logger::warn("Some registry settings could not be saved");
        }
    }

    bool Library::SaveScenes() const
    {
        std::shared_lock lock{ _mScenes };
        std::atomic_bool allSaved{ true };
        std::vector<std::jthread> threads;
        for (auto&& p : packages) {
            QueueRegistryJob(threads, [&p, &allSaved]() {
                bool saved = false;
                RunRegistryJob("Failed to save animation package settings", [&]() {
                    const auto filename = std::format("{}_{}.yaml", p->GetName().data(), p->GetHash());
                    const auto filepath = MakeSceneSettingsPath(SCENE_USER_CONFIG, filename);
                    YAML::Node data{};
                    for (auto&& scene : p->scenes) {
                        auto node = data[scene->id];
                        scene->Save(node);
                    }
                    saved = SaveRegistryYaml(filepath, data);
                });
                if (!saved) {
                    allSaved.store(false, std::memory_order_relaxed);
                }
            });
        }
        for (auto&& thread : threads) {
            thread.join();
        }
        const bool saved = allSaved.load(std::memory_order_relaxed);
        if (saved)
            logger::info("Saved scenes");
        return saved;
    }

    void Library::SaveExpressions() const noexcept
    {
        std::unique_lock lock{ _mExpressions };
        for (auto&& [id, expression] : expressions) {
            expression.Save(EXPRESSION_PATH, false);
        }
        logger::info("Saved expressions");
    }

    bool Library::SaveVoices() const
    {
        const std::shared_lock lock{ _mVoice };
        bool settingsSaved = false;
        RunRegistryJob("Failed to save voice profiles", [&]() {
            auto settings = ReadRegistryYaml(VOICE_SETTING_PATH, true).value_or(YAML::Node{});
            for (auto&& [name, voice] : voices) {
                const auto existing = std::as_const(settings)[name.data()];
                if (existing.IsDefined()) {
                    (void)existing.as<bool>();
                }
                auto voiceNode = settings[name.data()];
                voice.Save(voiceNode);
            }
            settingsSaved = SaveRegistryYaml(VOICE_SETTING_PATH, settings);
        });
        bool cacheSaved = false;
        RunRegistryJob("Failed to save NPC voice assignments", [&]() {
            auto cache = ReadRegistryYaml(VOICE_SETTINGS_CACHES_PATH, true).value_or(YAML::Node{});
            for (const auto& key : removedVoiceCacheKeys) {
                cache.remove(key);
            }
            for (auto&& [id, voice] : savedVoices) {
                auto form = RE::TESForm::LookupByID<RE::Actor>(id);
                if (!form)
                    continue;
                if (auto base = form->GetActorBase()) {
                    if (!base->IsUnique())
                        continue;
                }
                auto str = Util::FormToString(form);
                cache[str] = voice->GetId().data();
            }
            cacheSaved = SaveRegistryYaml(VOICE_SETTINGS_CACHES_PATH, cache);
        });
        if (settingsSaved && cacheSaved)
            logger::info("Saved voices");
        return settingsSaved && cacheSaved;
    }

}  // namespace Registry
