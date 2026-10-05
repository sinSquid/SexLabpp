"""Compile the actual bounds validity predicate (no Havok ABI claim)."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Registry/Util/RayCast/ObjectBound.cpp').read_text()
code=r'''
#include <cassert>
#include <cmath>
#include <limits>
#include <initializer_list>
namespace glm {struct vec3 {float x,y,z;};}
struct ObjectBound {
 glm::vec3 boundMin{0,0,0},boundMax{1,1,1},worldBoundMin{0,0,0},worldBoundMax{1,1,1},rotation{0,0,0};
 bool IsValid()const;
};
'''+function(source,'bool ObjectBound::IsValid() const')+r'''
int main(){ObjectBound valid;assert(valid.IsValid());
 for(auto member:{&ObjectBound::boundMin,&ObjectBound::boundMax,&ObjectBound::worldBoundMin,&ObjectBound::worldBoundMax,&ObjectBound::rotation}){
  for(auto axis:{&glm::vec3::x,&glm::vec3::y,&glm::vec3::z}){
   for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()}){
    auto bounds=valid;(bounds.*member).*axis=bad;assert(!bounds.IsValid());
   }
  }
 }
 auto zero=valid;zero.boundMax.x=0;assert(!zero.IsValid());
 auto reversed=valid;reversed.boundMin.z=2;assert(!reversed.IsValid());
 // Rotated opposite world corners need not be sorted along each world axis.
 valid.worldBoundMin={5,4,3};valid.worldBoundMax={2,1,0};assert(valid.IsValid());
}
'''
run('object_bound_validity',code)
print('PASS: actual ObjectBound validity rejects non-finite local/world/rotation data and preserves rotated world corners')
