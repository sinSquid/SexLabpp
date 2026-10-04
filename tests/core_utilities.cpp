#include "../src/Util/FragmentCombinations.h"
#include "../src/Util/RecordIO.h"
#include "../src/Util/RequiredMatching.h"
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstring>
#include <iostream>
#include <numeric>
#include <random>
#include <set>
#include <thread>
namespace logger
{
    template <class... T>
    void error(T&&...)
    {}
    template <class... T>
    void info(T&&...)
    {}
}
#include "../src/Util/DirtyFlag.h"
#include "../src/Util/SaveQueue.h"

struct Stream
{
    std::vector<char> bytes;
    size_t position = 0;
    uint32_t ReadRecordData(void* out, uint32_t size)
    {
        const auto n = std::min<size_t>(size, bytes.size() - position);
        std::memcpy(out, bytes.data() + position, n);
        position += n;
        return static_cast<uint32_t>(n);
    }
    bool WriteRecordData(const void* in, uint32_t size)
    {
        const auto* data = static_cast<const char*>(in);
        bytes.insert(bytes.end(), data, data + size);
        return true;
    }
};

bool Exhaustive(const std::vector<std::vector<size_t>>& graph, size_t slots, size_t required)
{
    std::vector<bool> used(graph.size());
    std::function<bool(size_t)> search = [&](size_t slot) {
        if (slot == slots)
            return std::all_of(used.begin(), used.begin() + required, [](bool x) { return x; });
        for (size_t actor = 0; actor < graph.size(); ++actor) {
            if (used[actor] || std::find(graph[actor].begin(), graph[actor].end(), slot) == graph[actor].end())
                continue;
            used[actor] = true;
            if (search(slot + 1))
                return true;
            used[actor] = false;
        }
        return false;
    };
    return search(0);
}

int main()
{
    std::mt19937 random(17);
    for (size_t slots = 1; slots <= 5; ++slots) {
        for (size_t count = slots; count <= slots + 3; ++count) {
            for (int trial = 0; trial < 500; ++trial) {
                std::vector<std::vector<size_t>> graph(count);
                for (auto& row : graph)
                    for (size_t p = 0; p < slots; ++p)
                        if (random() % 2)
                            row.push_back(p);
                const auto required = random() % (slots + 1);
                const auto result = Util::MatchRequired(graph, slots, required);
                assert(!result.empty() == Exhaustive(graph, slots, required));
                if (!result.empty()) {
                    std::set<int> actors(result.begin(), result.end());
                    assert(actors.size() == slots);
                    for (size_t p = 0; p < slots; ++p)
                        assert(std::find(graph[result[p]].begin(), graph[result[p]].end(), p) != graph[result[p]].end());
                    for (size_t a = 0; a < required; ++a) assert(actors.contains(static_cast<int>(a)));
                }
            }
        }
    }
    for (int trial = 0; trial < 200; ++trial) {
        std::vector<std::vector<int>> choices(1 + random() % 5);
        for (auto& choice : choices)
            for (int k = 0; k < 4; ++k) choice.push_back(random() % 6);
        std::set<std::vector<int>> exhaustive;
        std::vector<int> path;
        std::function<void(size_t)> visit = [&](size_t i) {
            if (i == choices.size()) {
                auto key = path;
                std::sort(key.begin(), key.end());
                exhaustive.insert(key);
                return;
            }
            for (int value : choices[i]) {
                path.push_back(value);
                visit(i + 1);
                path.pop_back();
            }
        };
        visit(0);
        assert(Util::UniqueFragmentCombinations(choices) == exhaustive);
    }
    std::vector<std::vector<int>> worst(5, std::vector<int>(24));
    for (auto& row : worst) std::iota(row.begin(), row.end(), 0);
    const auto start = std::chrono::steady_clock::now();
    const auto combinations = Util::UniqueFragmentCombinations(worst);
    assert(combinations.size() == 98280);
    std::cout << "5x24 index choices: " << combinations.size() << " unique keys vs 7962624 tuples, "
              << std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count() << "s\n";

    Stream stream;
    Util::WriteRecord(&stream, uint32_t{ 42 });
    Util::WriteRecordString(&stream, std::string("hello"));
    Util::RecordReader reader(&stream, static_cast<uint32_t>(stream.bytes.size()));
    assert(reader.Read<uint32_t>() == 42 && reader.String() == "hello" && reader.Remaining() == 0);
    bool failed = false;
    try {
        reader.Read<uint64_t>();
    } catch (const std::runtime_error&) {
        failed = true;
    }
    assert(failed);
    Stream bad;
    Util::WriteRecord(&bad, uint64_t{ 1ULL << 40 });
    Util::RecordReader badReader(&bad, static_cast<uint32_t>(bad.bytes.size()));
    failed = false;
    try {
        badReader.String();
    } catch (const std::runtime_error&) {
        failed = true;
    }
    assert(failed);

    const auto directory = std::filesystem::temp_directory_path() / ("sexlab-save-test-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    const auto path = directory / "settings.yaml";
    std::vector<std::thread> writers;
    for (int n = 0; n < 4; ++n) writers.emplace_back([&, n] {
        for (int i = 0; i < 100; ++i) Util::SaveQueue::Get().Submit(path, std::string(5000, static_cast<char>('a' + n)));
    });
    for (auto& writer : writers) writer.join();
    Util::SaveQueue::Get().Submit(path, "final snapshot\n");
    Util::SaveQueue::Get().Flush();
    std::ifstream file(path);
    std::string actual((std::istreambuf_iterator<char>(file)), {});
    assert(actual == "final snapshot\n");
    file.close();
    assert(!std::filesystem::exists(path.string() + ".tmp"));
    // Failed replacement does not erase the existing destination.
    std::filesystem::create_directory(directory / "blocked");
    std::ofstream(directory / "blocked" / "keep") << "preserve";
    failed = false;
    try {
        Util::AtomicWrite(directory / "blocked", "no");
    } catch (...) {
        failed = true;
    }
    assert(failed && std::filesystem::exists(directory / "blocked" / "keep"));
    // An older snapshot must never acknowledge an edit made after it was captured.
    Util::DirtyFlag dirty(true);
    const auto old = dirty;
    dirty = true;
    Util::SaveQueue::Get().Submit(path, "old", old.Receipt());
    Util::SaveQueue::Get().Flush();
    assert(!old && dirty);
    Util::SaveQueue::Get().Submit(path, "new", dirty.Receipt());
    Util::SaveQueue::Get().Flush();
    assert(!dirty);
    dirty = true;
    Util::SaveQueue::Get().Submit(directory / "blocked", "failed", dirty.Receipt());
    Util::SaveQueue::Get().Flush();
    assert(dirty);

    const auto archive = directory / "training";
    std::filesystem::create_directory(archive);
    Util::AtomicWrite(archive / "ML_TrainingData_0.csv", "original0");
    Util::AtomicWrite(archive / "ML_TrainingData_2.csv", "original2");
    std::vector<std::thread> archivers;
    for (int i = 0; i < 4; ++i) archivers.emplace_back([&] { Util::ArchiveWrite(archive, { "header", "new" }); });
    for (auto& writer : archivers) writer.join();
    auto read = [](const auto& p) { std::ifstream f(p); return std::string(std::istreambuf_iterator<char>(f), {}); };
    assert(read(archive / "ML_TrainingData_0.csv") == "original0");
    assert(read(archive / "ML_TrainingData_2.csv") == "original2");
    size_t csvCount = 0;
    for (const auto& entry : std::filesystem::directory_iterator(archive))
        if (entry.path().extension() == ".csv")
            ++csvCount;
    assert(csvCount == 6);
    // A non-directory parent forces failure. The batch survives, keeps its
    // cluster directory, and is written after recovery without losing new data.
    const auto blockedParent = directory / "unavailable";
    Util::AtomicWrite(blockedParent, "block");
    Util::SaveQueue::Get().SubmitArchive(blockedParent / "OldCluster", { "header", "old session" });
    Util::SaveQueue::Get().Flush();
    assert(Util::SaveQueue::Get().FailedArchiveCount() == 1);
    std::filesystem::remove(blockedParent);
    Util::SaveQueue::Get().SubmitArchive(blockedParent / "NewCluster", { "header", "new session" });
    Util::SaveQueue::Get().Flush();
    assert(Util::SaveQueue::Get().FailedArchiveCount() == 0);
    assert(read(blockedParent / "OldCluster" / "ML_TrainingData_0.csv") == "header\nold session\n");
    assert(read(blockedParent / "NewCluster" / "ML_TrainingData_0.csv") == "header\nnew session\n");
    std::filesystem::remove_all(directory);
    std::cout << "PASS: required matching, exact index equivalence, record bounds, serialized atomic saving\n";
}
