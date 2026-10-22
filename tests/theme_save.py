"""Production theme-save callback with deterministic queue and real atomic files."""
from pathlib import Path
import tempfile
from fork_review_regressions import function, run

code = r'''
#include <cassert>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>
#include <vector>
#include "Util/AtomicWrite.h"
namespace fs = std::filesystem;
namespace logger { template<class... T> void warn(T&&...) {} template<class... T> void error(T&&...) {} template<class... T> void info(T&&...) {} }
namespace Util::AsyncIO {
std::vector<std::function<void()>> queue;
void Submit(std::function<void()> task) { queue.push_back(std::move(task)); }
void Drain() { auto tasks = std::move(queue); queue.clear(); for(auto& task: tasks) task(); }
}
struct Data { std::string value; };
struct WriteOptions {};
Data data;
bool loaded = false;
bool IsLoaded() { return loaded; }
std::string THEME_PATH;
namespace glz {
bool fail = false;
template<auto> bool write(const Data& snapshot, std::string& buffer) { buffer = snapshot.value; return fail; }
std::string format_error(bool, const std::string&) { return "test serialization failure"; }
}
'''+function('src/Thread/Interface/UI/Theme.cpp', 'void Save()')+r'''
std::string read() { std::ifstream stream(THEME_PATH); return std::string(std::istreambuf_iterator<char>(stream), {}); }
int main(int argc, char** argv) {
    assert(argc == 2);
    const fs::path root = std::string(argv[1]) + ".data";
    THEME_PATH = (root / "theme.json").string();
    Save(); assert(Util::AsyncIO::queue.empty());
    loaded = true;
    data.value = "snapshot";
    Save(); data.value = "later";
    Util::AsyncIO::Drain(); assert(read() == "snapshot");
    glz::fail = true; Save(); Util::AsyncIO::Drain(); assert(read() == "snapshot");
    glz::fail = false; Save(); Util::AsyncIO::Drain(); assert(read() == "later");
    THEME_PATH = (root / "theme.json" / "cannot-write.json").string();
    Save(); Util::AsyncIO::Drain();
    THEME_PATH = (root / "theme.json").string(); assert(read() == "later");
    for(const auto& entry : fs::directory_iterator(root))
        assert(entry.path().filename() == "theme.json");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    run('theme_save', code, Path(tmp))
