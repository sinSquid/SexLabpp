#pragma once
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <type_traits>

namespace Util
{
    // Reads are bounded by the enclosing SKSE record, including allocation lengths.
    template <class Stream>
    class RecordReader
    {
      public:
        RecordReader(Stream* stream, uint32_t length) : stream(stream), remaining(length) {}
        void Bytes(void* value, uint32_t size)
        {
            if (size > remaining || stream->ReadRecordData(value, size) != size)
                throw std::runtime_error("Truncated serialization record");
            remaining -= size;
        }
        template <class T>
        T Read()
        {
            static_assert(std::is_trivially_copyable_v<T>);
            T value{};
            Bytes(&value, static_cast<uint32_t>(sizeof(T)));
            return value;
        }
        uint64_t Count(uint32_t minimumBytes = 1)
        {
            const auto count = Read<uint64_t>();
            if (minimumBytes == 0 || count > remaining / minimumBytes)
                throw std::runtime_error("Invalid serialization count");
            return count;
        }
        std::string String()
        {
            const auto size = Count();
            if (size == 0 || size > 1024 * 1024)
                throw std::runtime_error("Invalid serialization string length");
            std::string value(static_cast<size_t>(size), '\0');
            Bytes(value.data(), static_cast<uint32_t>(size));
            if (value.back() != '\0')
                throw std::runtime_error("Unterminated serialization string");
            value.pop_back();
            return value;
        }
        uint32_t Remaining() const { return remaining; }

      private:
        Stream* stream;
        uint32_t remaining;
    };

    template <class Stream, class T>
    void WriteRecord(Stream* stream, const T& value)
    {
        static_assert(std::is_trivially_copyable_v<T>);
        if (!stream->WriteRecordData(&value, static_cast<uint32_t>(sizeof(T))))
            throw std::runtime_error("Unable to write serialization record");
    }
    template <class Stream, class String>
    void WriteRecordString(Stream* stream, const String& value)
    {
        const auto length = value.length();
        if (length >= 1024 * 1024)
            throw std::runtime_error("Serialization string exceeds limit");
        const auto size = static_cast<uint64_t>(length) + 1;
        WriteRecord(stream, size);
        // String views need not have an accessible terminator, and empty
        // engine strings may have a null data pointer. Preserve the wire NUL.
        if (length && !stream->WriteRecordData(value.data(), static_cast<uint32_t>(length)))
            throw std::runtime_error("Unable to write serialization string");
        WriteRecord(stream, char{ '\0' });
    }
}
