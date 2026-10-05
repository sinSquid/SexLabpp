#pragma once
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <filesystem>
#include <fstream>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <system_error>
#include <thread>
#include <utility>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#endif

namespace Util
{
    inline void AtomicWrite(const std::filesystem::path& path, const std::string& bytes, bool overwrite = true)
    {
        if (!path.parent_path().empty())
            std::filesystem::create_directories(path.parent_path());
        // A writer owns its staging directory exclusively. Sharing path + ".tmp"
        // lets concurrent callers truncate, publish or remove each other's bytes.
        static std::atomic<uint64_t> nextTemporary{ 0 };
        std::filesystem::path staging;
        for (;;) {
            staging = path;
            staging += ".tmp-" + std::to_string(nextTemporary.fetch_add(1, std::memory_order_relaxed));
            std::error_code error;
            if (std::filesystem::create_directory(staging, error))
                break;
            if (error && error != std::errc::file_exists)
                throw std::system_error(error, "Reserve save staging directory");
        }
        const auto temporary = staging / "data";
        try {
            std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
            output.exceptions(std::ios::badbit | std::ios::failbit);
            output.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
            output.close();
#ifdef _WIN32
            const auto flags = MOVEFILE_WRITE_THROUGH | (overwrite ? MOVEFILE_REPLACE_EXISTING : 0);
            if (!::MoveFileExW(temporary.c_str(), path.c_str(), flags)) {
                const auto error = ::GetLastError();
                if (overwrite || (error != ERROR_FILE_EXISTS && error != ERROR_ALREADY_EXISTS))
                    throw std::system_error(static_cast<int>(error), std::system_category(), "Publish save file");
            }
#else
            if (overwrite) {
                std::filesystem::rename(temporary, path);
            } else {
                // Publishing a hard link is atomic and cannot replace another
                // writer's file; the staging copy is removed below.
                std::error_code error;
                std::filesystem::create_hard_link(temporary, path, error);
                if (error && error != std::errc::file_exists)
                    throw std::system_error(error, "Publish save file");
            }
#endif
        } catch (...) {
            std::error_code ignored;
            std::filesystem::remove_all(staging, ignored);
            throw;
        }
        std::error_code ignored;
        std::filesystem::remove_all(staging, ignored);
    }

    // Reserve a filename with an exclusive directory, then publish complete bytes
    // without replacing an existing file, even if another writer races us.
    inline std::filesystem::path ArchiveWrite(const std::filesystem::path& directory, const std::vector<std::string>& rows)
    {
        std::filesystem::create_directories(directory);
        std::string bytes;
        size_t size = 0;
        for (const auto& row : rows) size += row.size() + 1;
        bytes.reserve(size);
        for (const auto& row : rows) {
            bytes += row;
            bytes += '\n';
        }
        for (size_t id = 0;; ++id) {
            const auto path = directory / ("ML_TrainingData_" + std::to_string(id) + ".csv");
            if (std::filesystem::exists(path))
                continue;
            auto reservation = path;
            reservation += ".reserve";
            if (!std::filesystem::create_directory(reservation))
                continue;
            const auto temporary = reservation / "data";
            try {
                AtomicWrite(temporary, bytes);
#ifdef _WIN32
                if (!::MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_WRITE_THROUGH)) {
                    const auto error = ::GetLastError();
                    if (error != ERROR_FILE_EXISTS && error != ERROR_ALREADY_EXISTS)
                        throw std::system_error(static_cast<int>(error), std::system_category(), "Publish training data");
                    std::filesystem::remove_all(reservation);
                    continue;
                }
#else
                std::error_code error;
                std::filesystem::create_hard_link(temporary, path, error);
                if (error) {
                    if (error != std::errc::file_exists)
                        throw std::system_error(error);
                    std::filesystem::remove_all(reservation);
                    continue;
                }
#endif
                std::error_code ignored;
                std::filesystem::remove_all(reservation, ignored);
                return path;
            } catch (...) {
                std::error_code ignored;
                std::filesystem::remove_all(reservation, ignored);
                throw;
            }
        }
    }

    // One writer; pending snapshots of the same path collapse to the newest value.
    // Immutable snapshots cross the thread boundary. Destruction drains queued work.
    class SaveQueue
    {
      public:
        static SaveQueue& Get()
        {
            static SaveQueue queue;
            return queue;
        }
        void Submit(std::filesystem::path path, std::string bytes, std::shared_ptr<std::atomic_bool> receipt = {})
        {
            std::lock_guard lock(mutex);
            pending.insert_or_assign(std::move(path), Snapshot{ std::move(bytes), std::move(receipt) });
            changed.notify_all();
        }
        void SubmitArchive(std::filesystem::path directory, std::vector<std::string> rows)
        {
            std::lock_guard lock(mutex);
            RetryArchivesLocked();
            archives.push_back({ std::move(directory), std::move(rows) });
            changed.notify_all();
        }
        // Failures remain in memory, bound to their original cluster. Retry on
        // the next training-state change, or explicitly; never spin on failure.
        void RetryArchives()
        {
            std::lock_guard lock(mutex);
            RetryArchivesLocked();
            changed.notify_all();
        }
        size_t FailedArchiveCount()
        {
            std::lock_guard lock(mutex);
            return failedArchives.size();
        }
        void Flush()
        {
            std::unique_lock lock(mutex);
            changed.wait(lock, [&] { return pending.empty() && archives.empty() && !writing; });
        }
        ~SaveQueue()
        {
            {
                std::lock_guard lock(mutex);
                stopping = true;
                RetryArchivesLocked();
            }
            changed.notify_all();
            worker.join();
        }

      private:
        struct Snapshot
        {
            std::string bytes;
            std::shared_ptr<std::atomic_bool> receipt;
        };
        struct Archive
        {
            std::filesystem::path directory;
            std::vector<std::string> rows;
        };
        void RetryArchivesLocked()
        {
            while (!failedArchives.empty()) {
                archives.push_back(std::move(failedArchives.front()));
                failedArchives.pop_front();
            }
        }
        SaveQueue() : worker([this] { Run(); }) {}
        void Run()
        {
            std::unique_lock lock(mutex);
            for (;;) {
                changed.wait(lock, [&] { return stopping || !pending.empty() || !archives.empty(); });
                if (pending.empty() && archives.empty())
                    return;
                if (!archives.empty()) {
                    auto batch = std::move(archives.front());
                    archives.pop_front();
                    writing = true;
                    lock.unlock();
                    bool success = false;
                    try {
                        const auto path = ArchiveWrite(batch.directory, batch.rows);
                        logger::info("Saved ML training data to {}", path.string());
                        success = true;
                    } catch (const std::exception& error) {
                        logger::error("ML training save failed for {}; retaining batch for retry: {}", batch.directory.string(), error.what());
                    }
                    lock.lock();
                    if (!success)
                        failedArchives.push_back(std::move(batch));
                    writing = false;
                    changed.notify_all();
                    continue;
                }
                auto entry = pending.extract(pending.begin());
                writing = true;
                lock.unlock();
                try {
                    AtomicWrite(entry.key(), entry.mapped().bytes);
                    if (entry.mapped().receipt)
                        entry.mapped().receipt->store(true);
                } catch (const std::exception& error) {
                    logger::error("Save failed for {}: {}", entry.key().string(), error.what());
                }
                lock.lock();
                writing = false;
                changed.notify_all();
            }
        }
        std::mutex mutex;
        std::condition_variable changed;
        std::map<std::filesystem::path, Snapshot> pending;
        std::deque<Archive> archives, failedArchives;
        bool writing{ false };
        bool stopping{ false };
        std::thread worker;
    };
}
