#pragma once
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>
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

}
