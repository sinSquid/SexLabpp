#pragma once
#include <algorithm>
#include <memory>
#include <vector>

namespace Util
{
    // Caller owns the registry write lock. Undo records allocate before publication.
    template<class Package, class Packages, class IdMap, class OwnerMap, class Index, class Pending>
    void PublishPackage(std::unique_ptr<Package>& package, Packages& packages,
        IdMap& ids, OwnerMap& owners, Index& index, const Pending& pending)
    {
        struct IdUndo { typename IdMap::iterator it; bool inserted; typename IdMap::mapped_type old; };
        struct IndexUndo { typename Index::key_type key; bool inserted; typename Index::mapped_type* values; size_t size; };
        std::vector<IdUndo> idUndo;
        std::vector<typename OwnerMap::key_type> ownerUndo;
        std::vector<IndexUndo> indexUndo;
        idUndo.reserve(package->scenes.size());
        ownerUndo.reserve(package->scenes.size());
        indexUndo.reserve(pending.size());
        try {
            for (const auto& scene : package->scenes) {
                auto [it, inserted] = ids.try_emplace(scene->id, scene.get());
                idUndo.push_back({it, inserted, it->second});
                it->second = scene.get();
                if (owners.emplace(scene.get(), package.get()).second) ownerUndo.push_back(scene.get());
            }
            for (const auto& [key, scene] : pending) {
                auto [it, inserted] = index.try_emplace(key);
                auto& values = it->second;
                indexUndo.push_back({key, inserted, &values, values.size()});
                if (!std::ranges::contains(values, scene)) values.push_back(scene);
            }
            packages.push_back(std::move(package));
        } catch (...) {
            for (auto it = indexUndo.rbegin(); it != indexUndo.rend(); ++it) {
                if (it->inserted) index.erase(it->key);
                else it->values->resize(it->size);
            }
            for (auto key : ownerUndo) owners.erase(key);
            for (auto it = idUndo.rbegin(); it != idUndo.rend(); ++it) {
                if (it->inserted) ids.erase(it->it);
                else it->it->second = it->old;
            }
            throw;
        }
    }
}
