"""Exercise the production registry save/load entries with the actual yaml-cpp library on Windows."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile


root = Path(__file__).resolve().parents[1]
source = (root / 'src/Registry/Library_SaveLoad.cpp').read_text(encoding='utf-8-sig')


def function(signature, text=source):
    start = text.index(signature)
    end = text.index('{', start)
    depth = 1
    while depth:
        end += 1
        depth += (text[end] == '{') - (text[end] == '}')
    return text[start:end + 1]


code = r'''
#define NOMINMAX
#define YAML_CPP_STATIC_DEFINE
#include <Windows.h>
#include <yaml-cpp/yaml.h>
#include <atomic>
#include <cassert>
#include <filesystem>
#include <format>
#include <fstream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <shared_mutex>
#include <string>
#include <system_error>
#include <utility>
namespace fs = std::filesystem;
namespace logger {
    template <class... Args> void info(Args&&...) {}
    template <class... Args> void warn(Args&&...) {}
    template <class... Args> void error(Args&&...) {}
}
namespace RE {
    using BSFixedString = std::string;
    struct ActorBase { bool IsUnique() const { return true; } };
    struct Actor {
        unsigned id;
        ActorBase base;
        ActorBase* GetActorBase() { return &base; }
    };
    struct TESForm {
        template <class T> static T* LookupByID(unsigned id) {
            static T actor{1};
            return id == 1 ? &actor : nullptr;
        }
    };
}
namespace Util {
    unsigned FormFromString(const std::string& actor) { return actor == "live" ? 1 : (actor == "earlier" ? 2 : 0); }
    std::string FormToString(const RE::Actor*) { return "live"; }
}
struct Scene {
    std::string id;
    bool enabled{true};
    void Load(const YAML::Node& node) { enabled = node["enabled"].as<bool>(); }
};
struct Voice {
    std::string id;
    bool enabled{true};
    const std::string& GetId() const { return id; }
    void Load(const YAML::Node&);
    void Save(YAML::Node&) const;
};
struct Library {
    static inline fs::path SCENE_USER_CONFIG, VOICE_SETTING_PATH, VOICE_SETTINGS_CACHES_PATH;
    mutable std::shared_mutex _mScenes, _mVoice;
    std::map<std::string, Scene*> sceneMap;
    std::map<std::string, Voice> voices;
    std::map<unsigned, const Voice*> savedVoices;
    std::set<std::string> removedVoiceCacheKeys;
    void InitializeSceneSettings();
    void InitializeVoiceSettings();
    void InitializeVoiceCache();
    bool SaveVoices() const;
};
'''

for signature in (
    'template <class Job>\n        void RunRegistryJob',
    'fs::path RegistryIOPath(', 'std::string RegistryPathLabel(',
    'std::optional<YAML::Node> ReadRegistryYaml(', 'bool SaveRegistryYaml(',
    'void Library::InitializeSceneSettings(', 'void Library::InitializeVoiceSettings(',
    'void Library::InitializeVoiceCache(', 'bool Library::SaveVoices(',
):
    code += '\n' + function(signature)

voice_source = (root / 'src/Registry/Define/Voice.cpp').read_text(encoding='utf-8-sig')
for signature in ('void Voice::Load(', 'void Voice::Save('):
    code += '\n' + function(signature, voice_source)

code += r'''
void testSceneRoundtrip(const fs::path& directory) {
    Library library;
    Library::SCENE_USER_CONFIG = directory;
    Scene scene{"scene"};
    library.sceneMap.emplace(scene.id, &scene);
    const auto file = directory / (std::wstring(246, L'a') + L".yaml");
    const auto other = directory / L"\u4E2D\u6587.yaml";
    YAML::Node settings;
    settings[scene.id]["enabled"] = false;
    assert(SaveRegistryYaml(file, settings));
    library.InitializeSceneSettings();
    assert(!scene.enabled);
    assert(fs::remove(RegistryIOPath(file)));
    scene.enabled = true;
    assert(SaveRegistryYaml(other, settings));
    library.InitializeSceneSettings();
    assert(!scene.enabled);
}

std::string readBytes(const fs::path& file) {
    std::ifstream input(RegistryIOPath(file), std::ios::binary);
    return {std::istreambuf_iterator<char>{input}, {}};
}

void writeBytes(const fs::path& file, std::string_view bytes) {
    std::ofstream output(RegistryIOPath(file), std::ios::binary);
    output << bytes;
    output.close();
    assert(output);
}

void testVoiceRoundtrip(const fs::path& directory) {
    const auto settings = directory / "Voices.yaml";
    const auto cache = directory / "Voices_NPC.yaml";
    Library::VOICE_SETTING_PATH = settings;
    Library::VOICE_SETTINGS_CACHES_PATH = cache;
    Library library;
    library.voices.emplace("sample", Voice{"sample"});

    assert(!ReadRegistryYaml(settings) && !ReadRegistryYaml(cache));
    assert(library.SaveVoices());

    YAML::Node profiles, assignments;
    profiles["sample"] = false;
    profiles["future"] = true;
    assignments["live"] = "sample";
    assignments["unloaded"] = "sample";
    assert(SaveRegistryYaml(settings, profiles) && SaveRegistryYaml(cache, assignments));
    library.InitializeVoiceSettings();
    library.InitializeVoiceCache();
    assert(!library.voices.at("sample").enabled && library.savedVoices.at(1)->id == "sample");

    library.voices.at("sample").enabled = true;
    assert(library.SaveVoices());
    const auto updated = ReadRegistryYaml(settings).value();
    assert(updated["sample"].as<bool>());
    assert(updated["future"].as<bool>());
    assert(ReadRegistryYaml(cache).value()["unloaded"].as<std::string>() == "sample");

    const auto corrupt = std::string("sample: [unclosed");
    writeBytes(settings, corrupt);
    library.removedVoiceCacheKeys.insert("unloaded");
    assert(!library.SaveVoices());
    assert(readBytes(settings) == corrupt);
    assert(!ReadRegistryYaml(cache).value()["unloaded"].IsDefined());

    const std::string wrongVoice = "earlier: [invalid]\nsample: false\n";
    library.voices.emplace("earlier", Voice{"earlier"});
    writeBytes(settings, wrongVoice);
    library.InitializeVoiceSettings();
    assert(!library.voices.at("sample").enabled);
    assert(!library.SaveVoices() && readBytes(settings) == wrongVoice);

    for (const std::string_view multiple : {"sample: false\n---\nunclosed: [value\n",
                                            "sample: false\n---\nfuture: true\n"}) {
        writeBytes(settings, multiple);
        assert(!library.SaveVoices() && readBytes(settings) == multiple);
    }
    const std::string multipleAssignments = "live: sample\n---\nother: sample\n";
    writeBytes(cache, multipleAssignments);
    assert(SaveRegistryYaml(settings, profiles));
    assert(!library.SaveVoices() && readBytes(cache) == multipleAssignments);

    writeBytes(cache, "earlier: [invalid]\nlive: sample\n");
    library.savedVoices.clear();
    library.InitializeVoiceCache();
    assert(!library.savedVoices.contains(2) && library.savedVoices.at(1)->id == "sample");
    assert(library.SaveVoices());
    assert(ReadRegistryYaml(cache).value()["earlier"].IsSequence());

    library.voices.at("sample").enabled = true;
    assert(SaveRegistryYaml(settings, profiles));
    const auto native = RegistryIOPath(cache);
    const auto original = readBytes(cache);
    HANDLE handle = CreateFileW(native.c_str(), GENERIC_READ, 0, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    assert(handle != INVALID_HANDLE_VALUE);
    assert(!library.SaveVoices());
    assert(CloseHandle(handle));
    assert(readBytes(cache) == original);
    assert(ReadRegistryYaml(settings).value()["sample"].as<bool>());
}

int main() {
    const auto sceneDir = fs::path("scenes");
    testSceneRoundtrip(sceneDir);
    const auto voiceDir = fs::path("voice") / std::string(90, 'a') / std::string(90, 'b') / std::string(90, 'c');
    assert(fs::absolute(voiceDir).native().size() >= MAX_PATH);
    testSceneRoundtrip(voiceDir / "scenes");
    testVoiceRoundtrip(voiceDir);
}
'''

if override := os.environ.get('YAML_CPP_ROOT'):
    packages = [Path(override)]
else:
    local_cache = root.parent / (root.name + '-build-tools') / 'XmakePackages' / 'y' / 'yaml-cpp'
    packages = sorted(local_cache.glob('*/*'))
package = next((item for item in packages if (item / 'lib/yaml-cpp.lib').is_file()), None)
if package is None or not (package / 'include/yaml-cpp/yaml.h').is_file():
    raise SystemExit('Set YAML_CPP_ROOT to the installed static yaml-cpp package.')

with tempfile.TemporaryDirectory(prefix='registry-yaml-') as directory:
    path = Path(directory)
    cpp = path / 'registry_yaml.cpp'
    exe = path / 'registry_yaml.exe'
    try:
        cpp.write_text(code, encoding='utf-8')
        subprocess.run([os.environ.get('CXX', 'cl'), '/nologo', '/std:c++latest', '/EHsc', '/utf-8', '/MD',
                        '/D_ITERATOR_DEBUG_LEVEL=0', '/I' + str(package / 'include'), str(cpp),
                        str(package / 'lib/yaml-cpp.lib'), '/Fe:' + str(exe)], cwd=path, check=True)
        subprocess.run([str(exe)], cwd=path, check=True)
    finally:
        # TemporaryDirectory created this exact directory. Use the extended form to clean its long files.
        shutil.rmtree('\\\\?\\' + str(path), ignore_errors=False)

print('Production scene reload and voice merge passed for long paths, Unicode names, missing, malformed and locked files.')
