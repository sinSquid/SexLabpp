"""Execute production unregister paths across cancellation and ID reuse."""
from pathlib import Path
import tempfile
from fork_review_regressions import function, run

manager_file = 'src/Thread/Interaction/NiSurface/CollisionManager.cpp'
code = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <memory>
#include <mutex>
#include <ranges>
#include <vector>
namespace RE {
using FormID = uint32_t;
struct TESQuest { FormID id; FormID GetFormID() { return id; } };
}
namespace Thread::Interaction::NiSurface {
struct Scene { std::function<void()> onDestroy; ~Scene() { if(onDestroy) onDestroy(); } };
struct Manager {
    static inline std::mutex _mutex;
    static inline std::vector<std::pair<RE::FormID, std::shared_ptr<Scene>>> scenes;
    static void Unregister(RE::FormID, const Scene* = nullptr) noexcept;
    static std::shared_ptr<Scene> Get(RE::FormID);
};
'''+function(manager_file, 'void Manager::Unregister')+function(manager_file, 'std::shared_ptr<Scene> Manager::Get')+r'''
}
namespace Thread {
struct Instance {
    RE::TESQuest* linkedQst;
    std::weak_ptr<Interaction::NiSurface::Scene> ownedNiSurface;
    ~Instance() { UnregisterInstanceNiSurface(); }
'''+function('src/Thread/Thread.h', 'void UnregisterInstanceNiSurface()')+r'''
};
}
int main() {
    using namespace Thread::Interaction::NiSurface;
    RE::TESQuest quest{42};
    auto current = std::make_shared<Scene>();
    Manager::scenes.emplace_back(42, current);
    { Thread::Instance cancelled{&quest, {}}; }
    assert(Manager::Get(42) == current);
    auto old = std::make_shared<Scene>();
    { Thread::Instance superseded{&quest, old}; }
    assert(Manager::Get(42) == current);
    { Thread::Instance owner{&quest, current}; }
    assert(!Manager::Get(42));
    bool releasedOutsideLock = false;
    auto final = std::make_shared<Scene>();
    final->onDestroy = [&] {
        releasedOutsideLock = Manager::_mutex.try_lock();
        if (releasedOutsideLock) Manager::_mutex.unlock();
    };
    Manager::scenes.emplace_back(42, std::move(final));
    Manager::Unregister(42);
    assert(releasedOutsideLock);
    Manager::Unregister(999);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    run('scene_registration_owner', code, Path(tmp))
