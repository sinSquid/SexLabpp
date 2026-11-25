#include "RegistryYaml.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#include <atomic>
#include <fstream>
#include <system_error>

namespace Util
{
    fs::path RegistrySettingsPath(const fs::path& a_directory, std::string_view a_filename)
    {
        const fs::path filename{ a_filename };
        const auto& nativeName = filename.native();
        if (nativeName.empty() || nativeName == L"." || nativeName == L".." ||
            nativeName.find_first_of(LR"(\/:*?"<>|)") != std::wstring::npos ||
            std::ranges::any_of(nativeName, [](wchar_t c) { return c < 32; })) {
            throw std::invalid_argument("Invalid registry settings filename");
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

    std::optional<YAML::Node> ReadRegistryYaml(const fs::path& a_path, bool a_validateEntireFile)
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
