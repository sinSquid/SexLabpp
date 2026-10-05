"""Actual slider text formatting with actor/string stand-ins; no ImGui runtime."""
from source_regressions import ROOT, function, run

code = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
namespace RE {
struct Actor {uint32_t GetFormID() const {return 1;}};
using BSFixedString=std::string;
}
struct EnjBarsOverlay {
struct Bar {uint32_t formId=1; float enjoyment=0; char interactions[128]{}; bool isGameDpt=false;};
std::vector<Bar> _bars{1};
static constexpr float kGameEnjThresh=0;
void UpdateSlider(RE::Actor*,float,RE::BSFixedString);
};
''' + function((ROOT/'src/Thread/Interface/Elements/EnjBarsOverlay.cpp').read_text(),
               'void EnjBarsOverlay::UpdateSlider(') + r'''
int main() {
RE::Actor actor; EnjBarsOverlay overlay;
overlay.UpdateSlider(&actor,25,"a,b,c");
assert(std::string(overlay._bars[0].interactions)=="a \xC2\xB7 b \xC2\xB7 c");
for(size_t length=0;length<512;++length) {
 overlay.UpdateSlider(&actor,25,std::string(length,','));
 const std::string value=overlay._bars[0].interactions;
 assert(value.size()<=127 && value.size()%4==0);
 for(size_t i=0;i<value.size();i+=4) assert(value.substr(i,4)==" \xC2\xB7 ");
}
overlay.UpdateSlider(nullptr,25,"ignored");
}
'''
run('overlay_interaction_text', code)
print('PASS: actual slider formats spaced UTF-8 separators within buffer capacity')
