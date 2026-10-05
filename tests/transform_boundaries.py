"""Real transform setters/loader and finite predicate; YAML conversion stand-in."""
from source_regressions import ROOT, function, run

source=(ROOT/'src/Registry/Define/Transform.cpp').read_text()
header=(ROOT/'src/Registry/Define/Transform.h').read_text()
code=r'''
#include <cassert>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>
namespace logger {template<class...T>void warn(T&&...){}template<class...T>void error(T&&...){} }
namespace std {template<class E>int to_underlying(E e){return static_cast<int>(e);} }
namespace glm {struct vec3 {float x,y,z;};float radians(float d){return d*(3.14159265358979323846f/180.0f);} }
namespace YAML {
struct Node {
 bool defined=false,fail=false;float scalar=0;std::vector<Node> children;
 Node()=default;Node(float s):defined(true),scalar(s){}
 Node(std::vector<Node> c):defined(true),children(c){}
 Node operator[](const char* key)const{return children.at(key[0]=='L'?0:1);}
 Node operator[](int i)const{return children.at(i);}
 bool IsDefined()const{return defined;}size_t size()const{return children.size();}
 template<class T>T as()const{if(fail)throw std::runtime_error("bad YAML conversion");return static_cast<T>(scalar);}
};
}
namespace Registry {
enum CoordinateType {X,Y,Z,R};
struct Coordinate {glm::vec3 location{};float rotation{};Coordinate()=default;
 Coordinate(float x,float y,float z,float r):location{x,y,z},rotation(r){}
'''+function(header,'bool IsFinite() const')+r'''
};
struct Transform {Coordinate _offset{1,2,3,4};
 void SetOffset(const Coordinate&);void SetOffset(float,float,float,float);
 void SetOffset(float,CoordinateType);void Load(const YAML::Node&);
};
'''
for sig in ('void Transform::SetOffset(const Coordinate&', 'void Transform::SetOffset(float x',
            'void Transform::SetOffset(float a_value', 'void Transform::Load('):
    code+=function(source,sig)+'\n'
code+=r'''
}
int main(){
 Registry::Transform t;const auto unchanged=[&](){assert(t._offset.location.x==1&&t._offset.location.y==2&&t._offset.location.z==3&&t._offset.rotation==4);};
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()}){
  for(auto axis:{Registry::X,Registry::Y,Registry::Z,Registry::R}){t.SetOffset(bad,axis);unchanged();}
  t.SetOffset(1,bad,3,180);unchanged();
  t.SetOffset(Registry::Coordinate{1,2,3,bad});unchanged();
  YAML::Node node(std::vector<YAML::Node>{YAML::Node(std::vector<YAML::Node>{10,20,30}),YAML::Node(bad)});
  bool rejected=false;try{t.Load(node);}catch(const std::runtime_error&){rejected=true;}
  assert(rejected);unchanged();
 }
 YAML::Node invalid(std::vector<YAML::Node>{YAML::Node(std::vector<YAML::Node>{10,20,30}),YAML::Node(5)});
 invalid.children[0].children[1].fail=true;
 bool rejected=false;try{t.Load(invalid);}catch(const std::runtime_error&){rejected=true;}
 assert(rejected);unchanged();
 YAML::Node valid(std::vector<YAML::Node>{YAML::Node(std::vector<YAML::Node>{10,20,30}),YAML::Node(5)});
 t.Load(valid);assert(t._offset.location.x==10&&t._offset.location.y==20&&t._offset.location.z==30&&t._offset.rotation==5);
 t.SetOffset(1,2,3,180);assert(std::abs(t._offset.rotation-3.14159265f)<0.00001f);
 t.SetOffset(90,Registry::R);assert(std::abs(t._offset.rotation-1.57079633f)<0.00001f);
}
'''
run('transform_boundaries',code)
print('PASS: actual setters reject non-finite values; actual YAML loader preserves the prior offset on conversion/non-finite failure')
