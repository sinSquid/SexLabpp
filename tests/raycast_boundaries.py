"""Check the production layer mask and safe SIMD stores without engine calls."""
from pathlib import Path
import tempfile
from fork_review_regressions import ROOT, function, run

helper = function('src/Registry/Util/RayCast/bhkLinearCastCollector.h',
                  'constexpr bool IsRaycastLayerAccepted')
code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <xmmintrin.h>
'''+helper+r'''
int main() {
    for (uint32_t layer = 0; layer < 128; ++layer) {
        const bool expected = layer < 32 && ((0x40122716u >> (layer % 32)) & 1u);
        assert(IsRaycastLayerAccepted(layer) == expected);
        assert(IsRaycastLayerAccepted(layer | 0xFFFFFF80u) == expected);
    }
    alignas(16) float buffer[8]{};
    _mm_storeu_ps(buffer + 1, _mm_set_ps(4, 3, 2, 1));
    assert(buffer[1] == 1 && buffer[4] == 4);
}
'''
source = (ROOT / 'src/Registry/Util/RayCast/ObjectBound.cpp').read_text()
assert '_mm_store_ps(' not in source
assert source.count('_mm_storeu_ps(') == 5
body = function('src/Registry/Util/RayCast/ObjectBound.cpp',
                'RE::NiPointer<RE::NiCollisionObject> ObjectBound::GetCollisionNodeRecurse')
assert body.index('if (!a_node)') < body.index('a_node->collisionObject')
with tempfile.TemporaryDirectory() as tmp:
    run('raycast_boundaries', code, Path(tmp))
