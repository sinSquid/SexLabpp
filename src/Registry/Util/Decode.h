#pragma once

#include <fstream>
#include <string>
#include <type_traits>
#include <vector>
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace Decode
{
    static inline constexpr size_t HASH_SIZE = 4;
    static inline constexpr size_t ID_SIZE = 8;

    // Cache the file end for a complete package parse; avoid seeking to EOF for
    // every individual string while validating lengths before allocation.
    class InputBounds
    {
      public:
        static int Slot() { static const int slot = std::ios_base::xalloc(); return slot; }
        explicit InputBounds(std::ifstream& input) : stream(input), previous(input.pword(Slot()))
        {
            const auto position = stream.tellg();
            stream.seekg(0, std::ios::end);
            end = stream.tellg();
            stream.seekg(position);
            if (position < 0 || end < position || !stream)
                throw std::runtime_error("Invalid package stream extent");
            stream.pword(Slot()) = this;
        }
        ~InputBounds() { stream.pword(Slot()) = previous; }
        InputBounds(const InputBounds&) = delete;
        InputBounds& operator=(const InputBounds&) = delete;
        std::streampos End() const { return end; }
      private:
        std::ifstream& stream;
        void* previous;
        std::streampos end;
    };

    inline std::uint64_t Remaining(std::ifstream& stream)
    {
        if (auto* bounds = static_cast<InputBounds*>(stream.pword(InputBounds::Slot()))) {
            const auto position = stream.tellg();
            if (position < 0 || position > bounds->End())
                throw std::runtime_error("Invalid package read position");
            return static_cast<std::uint64_t>(bounds->End() - position);
        }
        InputBounds bounds(stream);
        return Remaining(stream);
    }

    inline void CheckCount(std::ifstream& stream, std::uint64_t count, std::uint64_t minimumBytes = 1)
    {
        if (minimumBytes == 0 || count > Remaining(stream) / minimumBytes)
            throw std::runtime_error("Package count exceeds remaining bytes");
    }

    template <typename I, std::enable_if_t<std::is_integral<I>::value, bool> = true>
    void Read(std::ifstream& a_stream, I& a_out)
    {
        constexpr size_t n = sizeof(I);
        static_assert(n <= sizeof(std::uint64_t));
        uint8_t buffer[n]{};
        if (!a_stream.read(reinterpret_cast<char*>(buffer), n))
            throw std::runtime_error("Truncated package integer");
        std::uint64_t bits = 0;
        for (size_t i = 0; i < n; i++) {
            bits = (bits << 8) | buffer[i];
        }
        a_out = static_cast<I>(bits);
    }

    template <typename F, std::enable_if_t<std::is_floating_point<F>::value, bool> = true>
    void Read(std::ifstream& a_stream, F& a_out)
    {
        int32_t tmp;
        Read(a_stream, tmp);
        a_out = static_cast<float>(tmp) / 1000.0f;
    }

    template <typename S, std::enable_if_t<std::is_same_v<S, std::string> || std::is_same_v<S, RE::BSFixedString>, bool> = true>
    void Read(std::ifstream& a_stream, S& a_out)
    {
        uint64_t u64;
        Read(a_stream, u64);
        CheckCount(a_stream, u64);
        if (u64 > static_cast<uint64_t>((std::numeric_limits<std::streamsize>::max)()))
            throw std::runtime_error("Package string exceeds stream capacity");
        std::vector<char> buffer;
        buffer.resize(u64);
        if (u64 && !a_stream.read(buffer.data(), static_cast<std::streamsize>(u64)))
            throw std::runtime_error("Truncated package string");
        a_out = std::string{ buffer.begin(), buffer.end() };
    }

    template <typename T>
    T Read(std::ifstream& a_stream)
    {
        T ret;
        Read(a_stream, ret);
        return ret;
    }

}  // namespace Decode
