#pragma once

#include <bit>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <type_traits>

namespace Decode
{
    static inline constexpr size_t HASH_SIZE = 4;
    static inline constexpr size_t ID_SIZE = 8;
    static inline constexpr uint64_t MAX_STRING_BYTES = 1024 * 1024;
    static inline constexpr uint64_t MAX_SCENES = 100000;
    static inline constexpr uint64_t MAX_TAGS = 4096;

    // One reader owns the cursor accounting for a package, including raw fields.
    // The underlying stream must not be read or repositioned while it is in use.
    class Reader
    {
      public:
        explicit Reader(std::ifstream& source) : stream(source)
        {
            const auto position = stream.tellg();
            if (position == std::streampos(-1))
                throw std::runtime_error("Invalid SLR stream position");
            stream.seekg(0, std::ios::end);
            const auto end = stream.tellg();
            stream.seekg(position);
            if (!stream || end < position)
                throw std::runtime_error("Invalid SLR stream length");
            remaining = static_cast<uint64_t>(end - position);
        }
        Reader(const Reader&) = delete;
        Reader& operator=(const Reader&) = delete;
        void read(char* destination, std::streamsize size)
        {
            if (size < 0 || static_cast<uint64_t>(size) > remaining)
                throw std::runtime_error("Truncated SLR field");
            stream.read(destination, size);
            if (!stream)
                throw std::runtime_error("Truncated SLR field");
            remaining -= static_cast<uint64_t>(size);
        }
        uint64_t Remaining() const { return remaining; }
        explicit operator bool() const { return static_cast<bool>(stream); }

      private:
        std::ifstream& stream;
        uint64_t remaining{ 0 };
    };

    inline uint64_t Remaining(const Reader& stream) { return stream.Remaining(); }

    inline void ValidateCount(Reader& stream, uint64_t count, uint64_t minimumBytes, uint64_t maximum)
    {
        if (!minimumBytes || count > maximum || count > Remaining(stream) / minimumBytes)
            throw std::runtime_error("Invalid SLR length or count");
    }

    template <typename I, std::enable_if_t<std::is_integral_v<I>, bool> = true>
    void Read(Reader& stream, I& out)
    {
        static_assert(!std::is_same_v<I, bool>);
        uint8_t buffer[sizeof(I)]{};
        stream.read(reinterpret_cast<char*>(buffer), sizeof(I));
        if (!stream)
            throw std::runtime_error("Truncated SLR integer");
        using U = std::make_unsigned_t<I>;
        U value = 0;
        for (size_t i = 0; i < sizeof(I); ++i) value = static_cast<U>((value << 8) | buffer[i]);
        out = std::bit_cast<I>(value);
    }

    template <typename F, std::enable_if_t<std::is_floating_point_v<F>, bool> = true>
    void Read(Reader& stream, F& out)
    {
        int32_t value;
        Read(stream, value);
        out = static_cast<F>(value) / static_cast<F>(1000);
    }

    template <typename S, std::enable_if_t<std::is_same_v<S, std::string> || std::is_same_v<S, RE::BSFixedString>, bool> = true>
    void Read(Reader& stream, S& out)
    {
        uint64_t size;
        Read(stream, size);
        ValidateCount(stream, size, 1, MAX_STRING_BYTES);
        std::string value(static_cast<size_t>(size), '\0');
        stream.read(value.data(), static_cast<std::streamsize>(size));
        if (!stream)
            throw std::runtime_error("Truncated SLR string");
        out = value;
    }

    template <typename T>
    T Read(Reader& stream)
    {
        T value;
        Read(stream, value);
        return value;
    }
}
