"""Actual file-stem predicate; Win32 name contract, not Windows I/O execution."""
import os
from pathlib import Path
from source_regressions import ROOT, function, run

source=Path(os.environ.get('STEM_SOURCE', ROOT/'src/Util/StringUtil.h')).read_text()
code=r'''
#include <cassert>
#include <string_view>
#include <initializer_list>
namespace Util {
''' + function(source,'constexpr bool IsSafeFileStem(') + r'''
}
int main() {
 for(const auto name:{"CON","con","PrN","AUX","NUL.txt","com1","LPT9.extra",
                      "COM\xC2\xB9","lpt\xC2\xB2","COM\xC2\xB3.yaml","NUL .txt"})
  assert(!Util::IsSafeFileStem(name));
 for(const auto name:{"CONSOLE","COM10","LPT0","_CON",".CON","CON_safe.yaml",
                      "normal","name.","name ","", ".", "..", "../x", "C:x"}) {
  const bool expected=std::string_view(name)!=""&&std::string_view(name)!="."&&
    std::string_view(name)!=".."&&std::string_view(name)!="../x"&&std::string_view(name)!="C:x";
  assert(Util::IsSafeFileStem(name)==expected);
 }
 // Scene filenames have a hash suffix, so a device-like display name remains valid.
 assert(Util::IsSafeFileStem("CON_ABCD.yaml"));
 static_assert(Util::IsSafeFileStem("normal"));
}
'''
run('windows_file_stems', code)
print('PASS: actual file-stem guard rejects Win32 reserved device names including extension/case/superscript forms')
