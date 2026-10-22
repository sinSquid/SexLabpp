"""Compile and execute the real RingBuffer header, including unused template APIs."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = r'''
#include "Util/RingBuffer.h"
#include <array>
#include <list>
#include <string>
using Buffer = Util::RingBuffer<int, 3>;
static_assert(!std::is_constructible_v<Buffer, int, int, int, int>);
int main() {
    Buffer empty;
    assert(empty.to<std::vector<int>>().empty());
    assert((empty.to<std::array<int, 3>>() == std::array<int, 3>{}));
    Buffer data(1, 2);
    auto copy = data;
    assert(copy.size() == 2 && copy.front() == 1 && copy.back() == 2);
    assert((data.to<std::array<int, 3>>() == std::array<int, 3>{1, 2, 0}));
    for (int i = 3; i <= 100; ++i) data.push(i);
    assert((data.to<std::vector<int>>() == std::vector<int>{98, 99, 100}));
    assert((data.to<std::list<int>>() == std::list<int>{98, 99, 100}));
    assert((data.to<std::array<int, 3>>() == std::array<int, 3>{98, 99, 100}));
    try { (void)data.to<std::array<int, 2>>(); assert(false); }
    catch (const std::length_error&) {}
    Util::RingBuffer<std::string, 1> single("first");
    single.push("next");
    assert(single.size() == 1 && single.front() == "next");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    source = Path(tmp) / 'test.cpp'
    binary = Path(tmp) / 'test'
    source.write_text(SOURCE, encoding='utf-8')
    subprocess.run([os.getenv('CXX', 'g++'), '-std=c++23', '-Wall', '-Wextra',
                    '-Werror', '-I', str(ROOT / 'src'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: real RingBuffer conversions, copy, wrapping, capacity constraints')
