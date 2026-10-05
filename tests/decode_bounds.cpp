#include <cassert>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <new>
#include <vector>
namespace RE
{
    struct BSFixedString
    {};
}
#include "../src/Registry/Util/Decode.h"
static bool audit = false;
static bool oversized = false;
void* operator new(std::size_t n)
{
    if (audit && n > 1024 * 1024) {
        oversized = true;
        throw std::bad_alloc();
    }
    if (auto* p = std::malloc(n ? n : 1))
        return p;
    throw std::bad_alloc();
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
int main()
{
    auto path = std::filesystem::temp_directory_path() / ("slr-bounds-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    auto write = [&](uint64_t count, const std::string& payload) {
        std::ofstream out(path, std::ios::binary);
        for (int shift = 56; shift >= 0; shift -= 8) out.put(static_cast<char>(count >> shift));
        out.write(payload.data(), static_cast<std::streamsize>(payload.size()));
    };
    for (auto count : { uint64_t{ 16777216 }, uint64_t{ 3 }, UINT64_MAX }) {
        write(count, "");
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        audit = true;
        bool rejected = false;
        std::string output = "unchanged";
        try {
            Decode::Read(input, output);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        audit = false;
        assert(rejected && !oversized && output == "unchanged");
    }
    write(3, "abc");
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        std::string output;
        Decode::Read(input, output);
        assert(output == "abc" && Decode::Remaining(input) == 0);
    }
    write(3, std::string("a\0b", 3));
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        std::string output = "unchanged";
        bool rejected = false;
        try { Decode::Read(input, output); }
        catch (const std::runtime_error&) { rejected = true; }
        assert(rejected && output == "unchanged");
    }
    write(0, "");
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        std::string output = "x";
        Decode::Read(input, output);
        assert(output.empty());
    }
    write(Decode::MAX_STRING_BYTES + 1, std::string(Decode::MAX_STRING_BYTES + 1, 'a'));
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        std::string output;
        bool rejected = false;
        try {
            Decode::Read(input, output);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        assert(rejected);
    }
    write(3, std::string(16, 'a'));
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        uint64_t count;
        Decode::Read(input, count);
        bool rejected = false;
        try {
            Decode::ValidateCount(input, count, 8, Decode::MAX_TAGS);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        assert(rejected);
        Decode::ValidateCount(input, 2, 8, Decode::MAX_TAGS);
    }
    {
        std::ofstream out(path, std::ios::binary);
        out.put('\xff');
        out.put('\xff');
        out.put('\xfc');
        out.put('\x18');
    }
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        float value = 0;
        Decode::Read(input, value);
        assert(value == -1.0f);
    }
    {
        std::ofstream out(path, std::ios::binary);
        out.put('\0');
    }
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        uint64_t value = 42;
        bool rejected = false;
        try {
            Decode::Read(input, value);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        assert(rejected && value == 42);
    }
    // Booleans consume one canonical byte without loading invalid bool representations.
    for (unsigned byte = 0; byte < 256; ++byte) {
        { std::ofstream out(path, std::ios::binary); out.put(static_cast<char>(byte)); }
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        bool value = false, rejected = false;
        try { Decode::Read(input, value); }
        catch (const std::runtime_error&) { rejected = true; }
        assert(rejected == (byte > 1));
        assert(value == (byte == 1));
        assert(input.Remaining() == 0);
    }
    // Raw fixed-size fields and typed reads must share the same remaining count.
    write(3, "abcXY");
    {
        std::ifstream file(path, std::ios::binary);
        Decode::Reader input(file);
        assert(input.Remaining() == 13);
        std::string value;
        Decode::Read(input, value);
        assert(value == "abc" && input.Remaining() == 2);
        char raw[3]{};
        input.read(raw, 1);
        assert(raw[0] == 'X' && input.Remaining() == 1);
        bool rejected = false;
        try {
            input.read(raw, 2);
        } catch (const std::runtime_error&) {
            rejected = true;
        }
        assert(rejected && input.Remaining() == 1);
        input.read(raw, 1);
        assert(raw[0] == 'Y' && input.Remaining() == 0);
    }
    // Construction at a nonzero stream offset measures only the unread suffix.
    {
        std::ifstream file(path, std::ios::binary);
        file.seekg(8);
        Decode::Reader input(file);
        assert(input.Remaining() == 5);
        char raw[5];
        input.read(raw, 5);
        assert(std::string(raw, 5) == "abcXY" && input.Remaining() == 0);
    }
    std::filesystem::remove(path);
    std::cout << "PASS: real SLR decode rejects oversized/truncated allocations, count bounds, valid/empty strings and signed fixed-point\n";
}
