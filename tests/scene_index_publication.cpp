// Standalone fault-injection regression for the production publication function.
#include "../src/Registry/SceneIndexPublication.h"
#include <cstdlib>
#include <map>
#include <memory>
#include <new>
#include <unordered_map>

namespace
{
    int allocationsBeforeFailure = -1;
    struct Scene { int id; };
    struct Package { std::vector<std::unique_ptr<Scene>> scenes; };

    void check(bool value)
    {
        if (!value)
            std::abort();
    }
}

void* operator new(std::size_t n)
{
    if (allocationsBeforeFailure == 0) {
        allocationsBeforeFailure = -1;
        throw std::bad_alloc();
    }
    if (allocationsBeforeFailure > 0)
        --allocationsBeforeFailure;
    if (void* p = std::malloc(n ? n : 1))
        return p;
    throw std::bad_alloc();
}

void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }

int main()
{
    for (int failAt = 0; ; ++failAt) {
        std::vector<std::unique_ptr<Package>> packages;
        packages.push_back(std::make_unique<Package>());
        const auto* original = packages.front().get();
        packages.front()->scenes.push_back(std::make_unique<Scene>(Scene{1}));
        auto* old = original->scenes.front().get();
        std::unordered_map<int, std::vector<Scene*>> buckets{{10, {old}}, {20, {}}};
        std::map<int, Scene*> byId{{1, old}};
        std::unordered_map<const Scene*, const Package*> owners{{old, original}};
        const auto oldBuckets = buckets;
        const auto oldIds = byId;
        const auto oldOwners = owners;
        auto package = std::make_unique<Package>();
        for (int id : {1, 2, 1, 2})
            package->scenes.push_back(std::make_unique<Scene>(Scene{id}));
        const std::vector<std::vector<int>> keys{{10, 30}, {20, 30}, {10, 40}, {20, 40}};
        allocationsBeforeFailure = failAt;
        try {
            Registry::PublishScenePackage(std::move(package), keys, packages, buckets, byId, owners);
        } catch (const std::bad_alloc&) {
            allocationsBeforeFailure = -1;
            check(packages.size() == 1 && packages.front().get() == original);
            check(buckets == oldBuckets && byId == oldIds && owners == oldOwners);
            continue;
        }
        allocationsBeforeFailure = -1;
        check(failAt > 0 && packages.size() == 2);
        const auto& added = packages.back()->scenes;
        check(byId.at(1) == added[2].get() && byId.at(2) == added[3].get());
        check(buckets.at(10) == std::vector<Scene*>{old, added[0].get(), added[2].get()});
        check(buckets.at(20) == std::vector<Scene*>{added[1].get(), added[3].get()});
        check(buckets.at(30) == std::vector<Scene*>{added[0].get(), added[1].get()});
        check(buckets.at(40) == std::vector<Scene*>{added[2].get(), added[3].get()});
        check(owners.at(old) == original);
        for (const auto& scene : added)
            check(owners.at(scene.get()) == packages.back().get());
        return 0;
    }
}
