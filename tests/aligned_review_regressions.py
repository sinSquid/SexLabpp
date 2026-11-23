"""MSVC harness for the reviewed startup and YAML save failure paths."""

import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def function(path, signature):
    source = (ROOT / path).read_text(encoding='utf-8-sig')
    first = source.index(signature)
    pos = source.index('{', first)
    depth = 1
    while depth:
        pos += 1
        depth += (source[pos] == '{') - (source[pos] == '}')
    return source[first:pos + 1]


code = r'''
#define NOMINMAX
#include <Windows.h>
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <filesystem>
#include <format>
#include <fstream>
#include <memory>
#include <mutex>
#include <ranges>
#include <shared_mutex>
#include <string>
#include <string_view>
#include <system_error>
#include <thread>
#include <unordered_map>
#include <vector>
namespace fs = std::filesystem;
namespace logger {
    template<class... Args> void warn(Args&&...) {}
    template<class... Args> void error(Args&&...) {}
    template<class... Args> void info(Args&&...) {}
}
namespace YAML {
    struct Node { std::string text; };
    struct Emitter {
        std::ostream& output;
        explicit Emitter(std::ostream& stream) : output(stream) {}
        void operator<<(const Node& node) { output << node.text; }
        bool good() const { return true; }
        std::string GetLastError() const { return {}; }
    };
}
'''

registry = 'src/Registry/Library_SaveLoad.cpp'
code += function(registry, 'template <class Job>\n        void QueueRegistryJob')
code += '\n' + function(registry, 'template <class Job>\n        void RunRegistryJob')
code += '\n' + function(registry, 'fs::path MakeSceneSettingsPath(')
code += '\n' + function(registry, 'fs::path RegistryIOPath(')
code += '\n' + function(registry, 'std::string RegistryPathLabel(')
code += '\n' + function(registry, 'bool SaveRegistryYaml(')
code += r'''
struct InlineJob {
    int& calls;
    explicit InlineJob(int& n) : calls(n) {}
    InlineJob(const InlineJob& rhs) : calls(rhs.calls) {
        throw std::system_error(std::make_error_code(std::errc::resource_unavailable_try_again));
    }
    InlineJob(InlineJob&&) = default;
    void operator()() const { ++calls; }
};

namespace RE {
    struct TESQuest {};
    struct BSSpinLockGuard { explicit BSSpinLockGuard(int&) {} };
    struct GraphNode { virtual ~GraphNode() = default; };
    struct hkbClipGenerator : GraphNode {
        hkbClipGenerator() = default;
        hkbClipGenerator(float speed, hkbClipGenerator* control) : playbackSpeed(speed), animationControl(control) {}
        float playbackSpeed{1.0f};
        hkbClipGenerator* animationControl{};
    };
    struct BSSynchronizedClipGenerator : GraphNode {
        explicit BSSynchronizedClipGenerator(hkbClipGenerator* clip) : clipGenerator(clip) {}
        hkbClipGenerator* clipGenerator;
    };
    struct hkbNodeInfo { GraphNode* nodeClone; };
    template<class T> using hkArray = std::vector<T>;
    struct BehaviorGraph { hkArray<hkbNodeInfo>* activeNodes{}; };
    struct BShkbAnimationGraph { BehaviorGraph* behaviorGraph{}; };
    struct BSAnimationGraphManager {
        struct RuntimeData { size_t activeGraph{}; int updateLock{}; } runtime;
        std::vector<std::unique_ptr<BShkbAnimationGraph>> graphs;
        RuntimeData& GetRuntimeData() { return runtime; }
    };
    using BSAnimationGraphManagerPtr = std::shared_ptr<BSAnimationGraphManager>;
    struct Actor {
        BSAnimationGraphManagerPtr manager;
        bool GetAnimationGraphManager(BSAnimationGraphManagerPtr& out) const { out = manager; return bool(out); }
        const char* GetDisplayFullName() const { return "Actor"; }
        unsigned GetFormID() const { return 1; }
    };
}
template<class T> T skyrim_cast(RE::GraphNode* source) { return dynamic_cast<T>(source); }
namespace Interface {
    struct FurnSelectMenu {
        struct Item { int value; };
        RE::TESQuest* _linkedThread{};
        uint64_t _ticket{};
        std::mutex _mutex;
        std::vector<Item> _items;
        bool registered{}, visible{};
        static FurnSelectMenu& GetSingleton() { static FurnSelectMenu menu; return menu; }
        void Show() { visible = registered; }
        void Hide() { visible = false; }
        bool IsVisible() const { return visible; }
        bool Open(RE::TESQuest*, uint64_t, std::vector<Item>);
        void Close(RE::TESQuest*, uint64_t);
    };
}
namespace Registry {
    struct ActorFragment {
        RE::Actor* actor;
        RE::Actor* GetActor() const { return actor; }
        bool IsSubmissive() const { return true; }
    };
    struct Scene {
        const char* id;
        const char* name{"test"};
        int score{};
        bool needsFurniture{};
        bool RequiresFurniture() const { return needsFurniture; }
        bool IsCompatibleFurniture(int) const { return true; }
        std::vector<int> FindAssignments(const std::vector<ActorFragment>& p, bool) const {
            assert(p.size() == 1 && p.front().actor);
            return score >= 145 ? std::vector{1} : std::vector<int>{};
        }
    };
    struct Library {
        std::vector<const Scene*> first, second;
        static Library* GetSingleton() { static Library library; return &library; }
        std::vector<const Scene*> LookupScenes(const std::vector<RE::Actor*>& actors,
            const std::vector<int>&, const std::vector<RE::Actor*>& subs) const {
            assert(actors.size() == 1);
            return subs.empty() ? second : first;
        }
    };
}
namespace Random {
    template<class T> auto draw(const T& entries) { assert(!entries.empty()); return entries.front(); }
}

struct Instance {
    enum SceneType { Primary, LeadIn, Custom, Total };
    enum class FurniturePreference { Disallow, Allow };
    using SceneMapping = std::array<std::vector<const Registry::Scene*>, Total>;
    struct SetupRequest { uint64_t ticket; int revision; };
    static inline std::recursive_mutex _mSetup;
    static inline std::shared_mutex _mInstances;
    static inline std::unordered_map<RE::TESQuest*, SetupRequest> setupRequests;
    static inline std::vector<std::unique_ptr<Instance>> pendingInstances, instances;
    static inline int resultCalls{};
    RE::TESQuest* linkedQst{};
    uint64_t setupTicket{};
    SceneMapping scenes;
    struct Position { Registry::ActorFragment data; bool playbackSpeedPending{}; };
    std::vector<Position> positions;
    float animationPlaybackSpeed{1.0f};
    struct Pending { bool playbackHeld; RE::hkbClipGenerator* observedGenerator; };
    std::vector<Pending> pendingAnimations;
    struct Center {
        struct Offset { int type{}; } offset;
        RE::Actor actor;
        RE::Actor* GetRef() { return &actor; }
    } center;
    bool activationAccepted{};
    bool SetActiveScene(const Registry::Scene*) { return activationAccepted; }
    static bool IsCurrentSetup(RE::TESQuest*, uint64_t, int) { return true; }
    static bool DispatchContinueSetup(RE::TESQuest*, bool result, int) {
        assert(!result);
        ++resultCalls;
        return false;
    }
    static bool HasSetupRequest(RE::TESQuest*, int);
    static void FailSetup(RE::TESQuest*, uint64_t, int);
    static auto LockState() { return std::unique_lock{_mSetup}; }
    std::vector<Registry::ActorFragment> InitializeScenes(const SceneMapping&, FurniturePreference);
    void FinalizeInstanceMake();
    void SetAnimationPlaybackSpeed(float);
};
'''

for path, signature in (
    ('src/Thread/Thread.cpp', 'bool Instance::HasSetupRequest('),
    ('src/Thread/Thread.cpp', 'void Instance::FailSetup('),
    ('src/Thread/ThreadCtor.cpp', 'std::vector<Registry::ActorFragment> Instance::InitializeScenes('),
    ('src/Thread/ThreadCtor.cpp', 'void Instance::FinalizeInstanceMake('),
    ('src/Thread/ThreadAnimation.cpp', 'void Instance::SetAnimationPlaybackSpeed('),
):
    code += '\n' + function(path, signature)

menu = 'src/Thread/Interface/FurnSelectMenu.cpp'
code += '\nnamespace Interface {\n' + function(menu, 'bool FurnSelectMenu::Open(')
code += '\n' + function(menu, 'void FurnSelectMenu::Close(') + '\n}\n'

code += r'''
void testWorkerFallback() {
    std::atomic<int> background{};
    int first{}, middle{};
    std::vector<std::jthread> workers;
    QueueRegistryJob(workers, InlineJob{first});
    QueueRegistryJob(workers, [&] { ++background; });
    QueueRegistryJob(workers, InlineJob{middle});
    QueueRegistryJob(workers, [&] { ++background; });
    for (auto& worker : workers) worker.join();
    assert(first == 1 && middle == 1 && background == 2);
}

void testGuardedLoader() {
    unsigned finished{};
    RunRegistryJob("Missing directory", [&] {
        fs::directory_iterator missing{L"missing-fixture-directory"};
        ++finished;
    });
    assert(finished == 0);
    RunRegistryJob("Subsequent loader", [&] { ++finished; });
    assert(finished == 1);
}

std::string load(const fs::path& path) {
    std::ifstream input(path, std::ios::binary);
    return {std::istreambuf_iterator<char>(input), {}};
}

void testYamlReplacement() {
    const fs::path file = L"test-output\\settings.yaml";
    assert(SaveRegistryYaml(file, YAML::Node{"old"}));
    const HANDLE reader = CreateFileW(file.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr,
                                      OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    assert(reader != INVALID_HANDLE_VALUE);
    assert(!SaveRegistryYaml(file, YAML::Node{"changed"}));
    assert(load(file) == "old");
    assert(std::distance(fs::directory_iterator(file.parent_path()), fs::directory_iterator{}) == 1);
    assert(CloseHandle(reader));
    assert(SaveRegistryYaml(file, YAML::Node{"new"}));
    assert(load(file) == "new");
    assert(!SaveRegistryYaml(file / "not-a-directory.yaml", YAML::Node{"bad"}));
    assert(load(file) == "new");
}

void testSceneSettingsFilename() {
    const fs::path directory = L"test-output";
    const std::string filename = "Test Pack_ABCD.yaml";
    assert(MakeSceneSettingsPath(directory, filename) == directory / filename);
    const std::vector<std::string> invalid = {
        R"(C:\fixture.yaml)", R"(\fixture.yaml)", R"(..\fixture.yaml)",
        "sub/fixture.yaml", "fixture:stream.yaml", std::string("fixture\0.yaml", 13)
    };
    for (const auto& candidate : invalid) {
        bool rejected{};
        try { (void)MakeSceneSettingsPath(directory, candidate); }
        catch (const std::invalid_argument&) { rejected = true; }
        assert(rejected);
    }

    // Feed the save function an ordinary path. Only the test's read and cleanup explicitly use the prefix.
    const auto longFile = MakeSceneSettingsPath(directory, std::string(246, 'a') + ".yaml");
    const fs::path fileOnDisk{LR"(\\?\)" + fs::absolute(longFile).native()};
    const bool first = SaveRegistryYaml(longFile, YAML::Node{"first"});
    const bool second = SaveRegistryYaml(longFile, YAML::Node{"second"});
    const auto result = load(fileOnDisk);
    fs::remove(fileOnDisk);
    assert(first && second && result == "second");
}

void testTicketRollback() {
    RE::TESQuest quest, other;
    Instance::setupRequests.emplace(&quest, Instance::SetupRequest{2, 9});
    Instance::setupRequests.emplace(&other, Instance::SetupRequest{3, 9});
    auto& menu = Interface::FurnSelectMenu::GetSingleton();
    assert(!menu.Open(&quest, 2, {{2}}) && !menu._linkedThread);
    menu.registered = true;
    assert(menu.Open(&other, 3, {{3}}));
    assert(!menu.Open(&quest, 2, {{2}}) && menu._items.front().value == 3);
    for (uint64_t ticket : {1, 2}) {
        auto pending = std::make_unique<Instance>();
        pending->linkedQst = &quest;
        pending->setupTicket = ticket;
        Instance::pendingInstances.push_back(std::move(pending));
    }
    Instance::FailSetup(&quest, 1, 9);
    assert(Instance::pendingInstances.size() == 1 && Instance::pendingInstances.front()->setupTicket == 2);
    assert(Instance::HasSetupRequest(&quest, 9) && Instance::resultCalls == 0);
    Instance::FailSetup(&quest, 2, 9);
    assert(Instance::pendingInstances.empty() && !Instance::HasSetupRequest(&quest, 9));
    assert(Instance::resultCalls == 1 && menu._linkedThread == &other && Instance::HasSetupRequest(&other, 9));
    menu.Close(&other, 2);
    assert(menu.IsVisible());
    menu.Close(&other, 3);
    assert(!menu.IsVisible());
    Instance::setupRequests.clear();
}

void testSceneFallback() {
    Registry::Scene low{"low", "Low", 140}, furniture{"bed", "Bed", 150, true};
    Registry::Scene good{"good", "Good", 150};
    auto* library = Registry::Library::GetSingleton();
    RE::Actor actor;
    Instance instance;
    instance.positions.push_back({{&actor}});
    library->first = {&low, &furniture};
    library->second = {};
    instance.InitializeScenes({}, Instance::FurniturePreference::Disallow);
    assert(instance.scenes[Instance::Primary].empty());
    library->second = {&low, &good};
    instance.InitializeScenes({}, Instance::FurniturePreference::Disallow);
    assert(instance.scenes[Instance::Primary] == std::vector<const Registry::Scene*>{&good});
    bool rejected{};
    try { instance.FinalizeInstanceMake(); } catch (const std::runtime_error&) { rejected = true; }
    assert(rejected);
    instance.activationAccepted = true;
    instance.FinalizeInstanceMake();
}

void testPlaybackGraphBounds() {
    RE::Actor empty{std::make_shared<RE::BSAnimationGraphManager>()};
    RE::Actor pastEnd{std::make_shared<RE::BSAnimationGraphManager>()};
    pastEnd.manager->graphs.push_back(std::make_unique<RE::BShkbAnimationGraph>());
    pastEnd.manager->runtime.activeGraph = pastEnd.manager->graphs.size();
    RE::Actor ready{std::make_shared<RE::BSAnimationGraphManager>()};
    RE::hkbClipGenerator control, playing{1.0f, &control}, held;
    RE::hkArray<RE::hkbNodeInfo> nodes{{&playing}, {&held}};
    RE::BehaviorGraph behavior{&nodes};
    ready.manager->graphs.push_back(std::make_unique<RE::BShkbAnimationGraph>(&behavior));
    Instance instance;
    instance.positions = {{{&empty}}, {{&pastEnd}}, {{&ready}}};
    instance.pendingAnimations.push_back({true, &held});
    instance.SetAnimationPlaybackSpeed(1.75f);
    assert(playing.playbackSpeed == 1.75f && control.playbackSpeed == 1.75f);
    assert(held.playbackSpeed == 0.0f);
    assert(instance.positions[1].playbackSpeedPending && !instance.positions[2].playbackSpeedPending);

    RE::hkbClipGenerator recoveredDirect, recoveredControl, recovered{1.0f, &recoveredControl}, recoveredHeld;
    RE::BSSynchronizedClipGenerator wrapped{&recovered}, wrappedHeld{&recoveredHeld};
    RE::hkArray<RE::hkbNodeInfo> recoveredNodes{{&recoveredDirect}, {&wrapped}, {&wrappedHeld}};
    RE::BehaviorGraph recoveredBehavior{&recoveredNodes};
    pastEnd.manager->graphs.front()->behaviorGraph = &recoveredBehavior;
    pastEnd.manager->runtime.activeGraph = 0;
    instance.pendingAnimations.push_back({true, &recoveredHeld});
    control.playbackSpeed = 1.5f;
    instance.SetAnimationPlaybackSpeed(1.75f);
    assert(recoveredDirect.playbackSpeed == 1.75f && recovered.playbackSpeed == 1.75f);
    assert(recoveredControl.playbackSpeed == 1.75f && recoveredHeld.playbackSpeed == 0.0f);
    assert(!instance.positions[1].playbackSpeedPending);
    assert(control.playbackSpeed == 1.5f && held.playbackSpeed == 0.0f);
}

int main() {
    testWorkerFallback();
    testGuardedLoader();
    testYamlReplacement();
    testSceneSettingsFilename();
    testTicketRollback();
    testSceneFallback();
    testPlaybackGraphBounds();
}
'''

with tempfile.TemporaryDirectory(prefix='aligned-review-') as directory:
    path = Path(directory)
    source = path / 'regressions.cpp'
    binary = path / 'regressions.exe'
    source.write_text(code, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'cl'), '/nologo', '/std:c++latest', '/EHsc', '/utf-8',
                    str(source), '/Fe:' + str(binary)], check=True, cwd=path)
    subprocess.run([str(binary)], check=True, cwd=path)

print('Worker fallback, loader exceptions, Windows YAML replacement and paths, ticket rollback, scene fallback and playback graph recovery passed.')
