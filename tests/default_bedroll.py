"""Verify the actual default offset and Coordinate constructor angle contract."""
from source_regressions import ROOT, run
source=(ROOT/'src/Registry/Define/Transform.cpp').read_text()
start=source.index('    Coordinate::Coordinate(float a_x')
end=source.index('    Coordinate::Coordinate(Decode::Reader&',start)
initializer=next(line for line in (ROOT/'src/Registry/Library.h').read_text().splitlines() if 'FurnitureDetails offsetDefaultBedroll' in line)
code=r'''
#include <cassert>
#include <cmath>
#include <numbers>
#include <vector>
namespace glm {struct vec3 {float x,y,z;};}
struct Coordinate {glm::vec3 location;float rotation;
 Coordinate(float,float,float,float);Coordinate(const std::vector<float>&);};
'''+source[start:end]+r'''
struct FurnitureType {enum Value {BedRoll};};
struct FurnitureDetails {Coordinate offset;FurnitureDetails(FurnitureType::Value,Coordinate c):offset(c){} };
struct Library {
'''+initializer+r'''
};
int main(){Library library;const auto angle=library.offsetDefaultBedroll.offset.rotation;
 assert(std::abs(angle-std::numbers::pi_v<float>)<0.00001f);
 assert(std::abs(std::sin(angle))<0.00001f&&std::cos(angle)<-0.9999f);
 assert(library.offsetDefaultBedroll.offset.location.z==7.5f);
}
'''
run('default_bedroll',code)
print('PASS: default bedroll half-turn uses radians and retains the vertical offset')
