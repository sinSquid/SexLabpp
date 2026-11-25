#pragma once

#include <filesystem>
#include <optional>
#include <string>
#include <string_view>
#include <yaml-cpp/yaml.h>

namespace Util
{
    std::filesystem::path RegistrySettingsPath(const std::filesystem::path& a_directory, std::string_view a_filename);
    std::filesystem::path RegistryIOPath(const std::filesystem::path& a_path);
    std::string RegistryPathLabel(const std::filesystem::path& a_path);
    std::optional<YAML::Node> ReadRegistryYaml(const std::filesystem::path& a_path, bool a_validateEntireFile = false);
    bool SaveRegistryYaml(const std::filesystem::path& a_path, const YAML::Node& a_data);
}
