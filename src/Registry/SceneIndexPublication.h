#pragma once

#include <cstddef>
#include <utility>
#include <vector>

namespace Registry
{
    // Caller holds the scene registry's exclusive lock. The local owner outlives rollback.
    template <class PackagePtr, class SceneKeys, class Buckets, class ById, class Owners>
    void PublishScenePackage(PackagePtr package, const SceneKeys& keys, std::vector<PackagePtr>& packages,
        Buckets& buckets, ById& byId, Owners& owners)
    {
        struct IdChange
        {
            typename ById::iterator entry;
            typename ById::mapped_type previous;
            bool inserted;
        };
        std::vector<IdChange> idChanges;
        idChanges.reserve(package->scenes.size());
        std::vector<const typename Buckets::key_type*> newBuckets;
        std::size_t started = 0;
        try {
            for (const auto& scene : package->scenes) {
                const auto& sceneKeys = keys[started];
                ++started;  // Include this scene even if only some bucket appends succeed.
                for (const auto& key : sceneKeys) {
                    auto bucket = buckets.find(key);
                    if (bucket == buckets.end()) {
                        // Record the key before either the map or the bucket vector can allocate.
                        newBuckets.push_back(&key);
                        bucket = buckets.try_emplace(key).first;
                    }
                    bucket->second.push_back(scene.get());
                }
                auto [entry, inserted] = byId.try_emplace(scene->id, nullptr);
                idChanges.push_back({ entry, entry->second, inserted });
                entry->second = scene.get();
                owners.emplace(scene.get(), package.get());
            }
            packages.push_back(std::move(package));
        } catch (...) {
            // Duplicate IDs within a package must unwind in reverse assignment order.
            for (auto it = idChanges.rbegin(); it != idChanges.rend(); ++it) {
                if (it->inserted)
                    byId.erase(it->entry);
                else
                    it->entry->second = it->previous;
            }
            while (started > 0) {
                const auto i = --started;
                const auto* scene = package->scenes[i].get();
                owners.erase(scene);
                for (const auto& key : keys[i]) {
                    auto bucket = buckets.find(key);
                    if (bucket != buckets.end() && !bucket->second.empty() && bucket->second.back() == scene)
                        bucket->second.pop_back();
                }
            }
            for (const auto* key : newBuckets)
                buckets.erase(*key);
            throw;
        }
    }
}
