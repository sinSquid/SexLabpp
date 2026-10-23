"""Check the production logging join with a non-NUL-terminated string view."""
from pathlib import Path
import tempfile
from fork_review_regressions import ROOT, run

source = (ROOT / 'src/Registry/Library.cpp').read_text()
start = source.index('[](std::string a, std::string_view b)')
end = source.index('\n            });', start)
join = source[start:end] + '\n}'
code = '''
#include <cassert>
#include <string>
#include <string_view>
int main() {
    auto join = ''' + join + ''';
    const char raw[] = {'a', 'b', 'c'};
    assert(join("first", std::string_view(raw, 3)) == "first, abc");
    const std::string text = "visible-hidden";
    assert(join("first", std::string_view(text).substr(0, 7)) == "first, visible");
    assert(join("first", {}) == "first, ");
}
'''
with tempfile.TemporaryDirectory() as tmp:
    run('tag_log_views', code, Path(tmp))
