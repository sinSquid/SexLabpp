"""Exercise production tag set operations with opaque engine-string stand-ins."""
from pathlib import Path
import re
import tempfile
from fork_review_regressions import ROOT, run

header = (ROOT / 'src/Registry/Define/Tags.h').read_text().replace('#pragma once', '')
source = (ROOT / 'src/Registry/Define/Tags.cpp').read_text()
source = re.sub(r'^#include.*$', '', source, flags=re.M)
code = r'''
#include <algorithm>
#include <array>
#include <bit>
#include <cassert>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <functional>
#include <map>
#include <ranges>
#include <regex>
#include <string>
#include <type_traits>
#include <vector>
#define _NODISCARD [[nodiscard]]
namespace RE { using BSFixedString = std::string; }
using FixedStringCompare = std::less<std::string>;
namespace stl {
template<class E> struct enumeration {
    using U = std::underlying_type_t<E>;
    U value{};
    E get() const { return static_cast<E>(value); }
    U underlying() const { return value; }
    void set(E x) { value |= static_cast<U>(x); }
    void reset(E x) { value &= ~static_cast<U>(x); }
    bool all(E x) const { return (value & static_cast<U>(x)) == static_cast<U>(x); }
    bool any(E x) const { return (value & static_cast<U>(x)) != 0; }
    enumeration operator&(enumeration b) const { return {value & b.value}; }
};
}
#include "Registry/Util/Decode.h"
#include "Util/StringUtil.h"
'''+header+source+r'''
int main() {
    using namespace Registry;
    for (uint64_t a = 0; a < 32; ++a) {
        for (uint64_t b = 0; b < 32; ++b) {
            TagData first, second;
            first.AddTag(static_cast<Tag>(a));
            second.AddTag(static_cast<Tag>(b));
            first.AddTag("custom-a"); second.AddTag("custom-b");
            first.AddAnnotation("shared"); second.AddAnnotation("shared");
            first.IntersectTags(second);
            for (uint64_t bit = 1; bit < 32; bit <<= 1)
                assert(first.HasTag(static_cast<Tag>(bit)) == bool(a & b & bit));
            assert(!first.HasTag("custom-a") && first.HasAnnotation("shared"));
        }
    }
    TagData value;
    value.AddTag("one"); value.AddTag("two"); value.AddTag("three");
    value.AddTag(static_cast<Tag>(31)); value.AddAnnotation("keep-annotation");
    value.AddTag(value);
    assert(value.AsVector().size() == 8);
    value.IntersectTags(value);
    assert(value.HasTag("one"));
    value.RemoveTag(value);
    assert(value.AsVector().empty() && value.HasAnnotation("keep-annotation"));
}
'''
with tempfile.TemporaryDirectory() as tmp:
    run('tag_sets', code, Path(tmp))
