#pragma once
#include <algorithm>
#include <atomic>
#include <exception>
#include <filesystem>
#include <mutex>
#include <thread>
#include <vector>

namespace Util
{
    struct FileListing {
        std::vector<std::filesystem::directory_entry> files;
        std::error_code error;
    };
    inline FileListing ListFiles(const std::filesystem::path& path, bool recursive)
    {
        FileListing result;
        const auto collect = [&]<class Iterator>() {
            Iterator it(path, result.error), end;
            while (!result.error && it != end) {
                std::error_code statusError;
                if (it->is_regular_file(statusError))
                    result.files.push_back(*it);
                if (statusError) { result.error = statusError; break; }
                it.increment(result.error);
            }
        };
        if (recursive) collect.template operator()<std::filesystem::recursive_directory_iterator>();
        else collect.template operator()<std::filesystem::directory_iterator>();
        return result;
    }

    template<class Function>
    void ForEachBounded(size_t count, Function&& function, size_t maximumWorkers = 8)
    {
        if (!count) return;
        std::atomic_size_t next{0};
        std::mutex errorMutex;
        std::exception_ptr error;
        const auto worker = [&] {
            for (;;) {
                const auto i = next.fetch_add(1, std::memory_order_relaxed);
                if (i >= count) return;
                try { function(i); }
                catch (...) {
                    std::lock_guard lock{errorMutex};
                    if (!error) error = std::current_exception();
                }
            }
        };
        {
            std::vector<std::jthread> workers;
            const auto limit = std::min(count, std::max(size_t{1}, maximumWorkers));
            workers.reserve(limit - 1);
            try {
                for (size_t i = 1; i < limit; ++i) workers.emplace_back(worker);
            } catch (const std::system_error&) {
                // Existing workers and this caller still consume the whole queue.
            }
            worker();
        }
        if (error) std::rethrow_exception(error);
    }
}
