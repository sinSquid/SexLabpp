from statistics_roundtrip import ROOT, function, run

SUPPORT = r'''
#include <algorithm>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <optional>
#include <random>
struct Vec {
 float x{},y{},z{};
 Vec operator+(Vec b)const{return {x+b.x,y+b.y,z+b.z};}
 Vec operator-(Vec b)const{return {x-b.x,y-b.y,z-b.z};}
 Vec operator*(float s)const{return {x*s,y*s,z*s};}
 bool operator==(const Vec&)const=default;
 float Dot(Vec b)const{return x*b.x+y*b.y+z*b.z;}
 float SqrLength()const{return Dot(*this);}
 float Length()const{return std::sqrt(SqrLength());}
 float GetDistance(Vec b)const{return (*this-b).Length();}
};
namespace RE {using NiPoint3=Vec;float rad_to_deg(float x){return x*180.0f/3.14159265358979323846f;}}
'''

def closest_segments():
    header=(ROOT/'src/Thread/Interaction/NiSurface/GeometryMath.h').read_text()
    source=(ROOT/'src/Thread/Interaction/NiSurface/GeometryMath.cpp').read_text()
    code=SUPPORT+function(header,'struct Segment')+';\n'
    code+=function(source,'Segment ClosestSegmentBetweenSegments(')+r'''
int main(){
 Segment a{{0,0,0},{2,0,0}},b{{1,-2,0},{1,2,0}};
 assert(ClosestSegmentBetweenSegments(a,b).Length()<0.00001f);
 Segment p{{-1,0,0}},q{{0,0,0}};
 assert(std::abs(ClosestSegmentBetweenSegments(p,q).Length()-1)<0.00001f);
 std::mt19937 rng(91);std::uniform_real_distribution<float> random(-5,5);
 auto point=[&]{return Vec{random(rng),random(rng),random(rng)};};
 for(int n=0;n<1000;++n){
  Segment x{point(),point()},y{point(),point()};
  if(n%10==0)y.end=y.start+x.Vector();
  if(n%17==0)x.end=x.start;
  auto nearest=ClosestSegmentBetweenSegments(x,y);
  float d=nearest.Vector().SqrLength();
  assert(std::abs(d-ClosestSegmentBetweenSegments(y,x).Vector().SqrLength())<0.001f);
  for(int i=0;i<=100;++i){float t=i/100.f;
   assert(d<=(x.start+x.Vector()*t-nearest.end).SqrLength()+0.001f);
   assert(d<=(y.start+y.Vector()*t-nearest.start).SqrLength()+0.001f);
  }
 }
}
'''
    run('nisurface_closest_segments',code)
    print('PASS: actual NiSurface closest segments; crossing/point/parallel and 1000 symmetry/optimality cases')

def angles_and_projection():
    source=(ROOT/'src/Thread/Interaction/NiSurface/GeometryMath.cpp').read_text()
    code=SUPPORT+function(source,'float GetAngleDegree(')+'\n'+function(source,'RE::NiPoint3 ProjectedComponent(')+r'''
int main(){
 assert(GetAngleDegree({},{1,0,0})==0);
 assert(std::abs(GetAngleDegree({1,0,0},{0,1,0})-90)<0.0001f);
 assert(std::abs(GetAngleDegree({1,0,0},{-1,0,0})-180)<0.0001f);
 assert(ProjectedComponent({1,2,3},{})==Vec{});
 assert((ProjectedComponent({1,2,3},{0,2,0})==Vec{0,2,0}));
}
'''
    run('nisurface_angles_projection',code)
    print('PASS: actual NiSurface angle/projection zero-axis and degree contracts')

if __name__=='__main__':
    closest_segments()
    angles_and_projection()
