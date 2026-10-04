#pragma once
#include <condition_variable>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <string>
#include <system_error>
#include <thread>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#endif

namespace Util
{
    inline void AtomicWrite(const std::filesystem::path& path, const std::string& bytes)
    {
        if (!path.parent_path().empty())
            std::filesystem::create_directories(path.parent_path());
        auto temporary = path;
        temporary += ".tmp";
        try {
            std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
            output.exceptions(std::ios::badbit | std::ios::failbit);
            output.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
            output.close();
#ifdef _WIN32
            if (!::MoveFileExW(temporary.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
                throw std::system_error(static_cast<int>(::GetLastError()), std::system_category(), "Replace save file");
#else
            std::filesystem::rename(temporary, path);
#endif
        } catch (...) {
            std::error_code ignored;
            std::filesystem::remove(temporary, ignored);
            throw;
        }
    }

    // One writer; pending snapshots of the same path collapse to the newest value.
    // Only immutable bytes cross the thread boundary. Destruction drains the queue.
    class SaveQueue
    {
      public:
        static SaveQueue& Get()
        {
            static SaveQueue queue;
            return queue;
        }
        void Submit(std::filesystem::path path, std::string bytes)
        {
            std::lock_guard lock(mutex);
            pending.insert_or_assign(std::move(path), std::move(bytes));
            changed.notify_all();
        }
        void Flush()
        {
            std::unique_lock lock(mutex);
            changed.wait(lock, [&] { return pending.empty() && !writing; });
        }
        ~SaveQueue()
        {
            {
                std::lock_guard lock(mutex);
                stopping = true;
            }
            changed.notify_all();
            worker.join();
        }

      private:
        SaveQueue() : worker([this] { Run(); }) {}
        void Run()
        {
            std::unique_lock lock(mutex);
            for (;;) {
                changed.wait(lock, [&] { return stopping || !pending.empty(); });
                if (pending.empty())
                    return;
                auto entry = pending.extract(pending.begin());
                writing = true;
                lock.unlock();
                try {
                    AtomicWrite(entry.key(), entry.mapped());
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
        std::map<std::filesystem::path, std::string> pending;
        bool writing{ false };
        bool stopping{ false };
        std::thread worker;
    };
}
