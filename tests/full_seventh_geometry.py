"""Production skeleton-chain traversal with engine stand-ins (also run under ASan)."""
import os
from pathlib import Path
import subprocess

from source_regressions import ROOT, function, run


def source(path):
    if os.getenv('REVIEW_BASE_DIR'):
        return (Path(os.environ['REVIEW_BASE_DIR']) / path).read_text()
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(
            ['git', 'show', f"{os.environ['REVIEW_BASE']}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


support = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <memory>
#include <span>
#include <utility>
#include <vector>
struct Vec {
 float x=0,y=0,z=0;
 float& operator[](size_t i){return i==0?x:i==1?y:z;}
 float operator[](size_t i)const{return i==0?x:i==1?y:z;}
 bool operator==(const Vec&)const=default;
 Vec operator+(Vec b)const{return{x+b.x,y+b.y,z+b.z};}
 Vec operator-(Vec b)const{return{x-b.x,y-b.y,z-b.z};}
 Vec operator*(float s)const{return{x*s,y*s,z*s};}
 Vec& operator+=(Vec b){return *this=*this+b;}
 Vec& operator/=(float s){return *this=*this*(1/s);}
 float SqrLength()const{return x*x+y*y+z*z;}
 float Length()const{return std::sqrt(SqrLength());}
 float GetDistance(Vec b)const{return (*this-b).Length();}
 float Dot(Vec b)const{return x*b.x+y*b.y+z*b.z;}
 void Unitize(){const auto length=Length();if(length>0)*this/=length;}
 static Vec Zero(){return {};}
};
struct Mat {
 float entry[3][3]={{1,0,0},{0,1,0},{0,0,1}};
 Mat()=default;
 Mat(Vec a,Vec b,Vec c){for(int i=0;i<3;++i){entry[0][i]=a[i];entry[1][i]=b[i];entry[2][i]=c[i];}}
 Vec operator[](int i)const{return {entry[0][i],entry[1][i],entry[2][i]};}
 Vec operator*(Vec v)const{Vec out{};for(int i=0;i<3;++i)for(int j=0;j<3;++j)out[i]+=entry[i][j]*v[j];return out;}
 Mat operator*(float s)const{auto out=*this;for(auto& row:out.entry)for(auto& v:row)v*=s;return out;}
 Mat operator*(const Mat& rhs)const{auto out=*this*0;for(int i=0;i<3;++i)for(int j=0;j<3;++j)for(int k=0;k<3;++k)out.entry[i][j]+=entry[i][k]*rhs.entry[k][j];return out;}
 Vec GetVectorY()const{return {0,1,0};}
};
namespace glm {using mat3=Mat;}
namespace RE {
 using NiPoint3=Vec;using NiMatrix3=Mat;
 template<class T>using NiPointer=std::shared_ptr<T>;
 struct Ref {uint32_t GetFormID()const{return 1;}};
 struct NiNode:std::enable_shared_from_this<NiNode> {
  struct {Mat rotate;Vec translate;} world;
  std::vector<NiPointer<NiNode>> children;
  auto& GetChildren(){return children;}
  NiPointer<NiNode> AsNode(){return shared_from_this();}
  Ref* GetUserData(){return nullptr;}
 };
}
namespace logger {template<class...T>void error(T&&...){} }
namespace NiMath {
 SEGMENT_DEFINITION
 Segment BestFit(std::span<const RE::NiPoint3>);
 float GetAngleDegree(Vec a,Vec b){
  const auto squared=a.SqrLength()*b.SqrLength();
  return squared>0 ? std::acos(std::clamp(a.Dot(b)/std::sqrt(squared),-1.f,1.f))*180.f/3.14159265f : 0;
 }
}
struct NodeData {
 struct SchlongData {
  Mat rot;std::vector<RE::NiPointer<RE::NiNode>> nodes;
  SchlongData()=default;
  SchlongData(RE::NiPointer<RE::NiNode>,const glm::mat3&);
  NiMath::Segment GetReferenceSegment()const;
 };
};
constexpr float MIN_SCHLONG_LEN=13;
'''
support = support.replace('SEGMENT_DEFINITION', function(
    source('src/Thread/NiNode/NiMath.h'), 'struct Segment :') + ';')

cases = r'''
std::shared_ptr<RE::NiNode> node(float y){
 auto result=std::make_shared<RE::NiNode>();result->world.translate={0,y,0};return result;
}
int main(){
 // A two-node chain forces the initial single-element vector to grow.
 auto root=node(0),child=node(1);root->children.push_back(child);
 NodeData::SchlongData pair(root,Mat{});
 assert(pair.nodes.size()==2&&pair.nodes.front()==root&&pair.nodes.back()==child);
 // Repeated growth must keep the current parent valid and traverse every node.
 auto longRoot=node(0),tail=longRoot;
 std::vector<RE::NiPointer<RE::NiNode>> expected{longRoot};
 for(int index=1;index<80;++index){auto next=node(float(index));tail->children.push_back(next);tail=next;expected.push_back(next);}
 NodeData::SchlongData chain(longRoot,Mat{});assert(chain.nodes==expected);
 // Multi-child traversal skips null/backwards children and chooses a forward node.
 root=node(0);auto backwards=node(-1),forward=node(1),tip=node(2);
 root->children={nullptr,backwards,forward};forward->children={tip};
 NodeData::SchlongData branched(root,Mat{});
 assert((branched.nodes==std::vector<RE::NiPointer<RE::NiNode>>{root,forward,tip}));
 // No eligible continuation terminates without growing the chain.
 root=node(0);root->children={nullptr,backwards};
 NodeData::SchlongData stopped(root,Mat{});assert(stopped.nodes.size()==1);
 root=node(0);root->children={nullptr};
 NodeData::SchlongData nullChild(root,Mat{});assert(nullChild.nodes.size()==1);
 std::cout<<"PASS: production skeleton-chain traversal retains parent ownership across growth and handles branches\n";
}
'''

for path, label in (
    ('src/Thread/NiNode/Node.cpp', 'new'),
    ('src/Thread/NiNode/Legacy/LegacyNode.cpp', 'legacy'),
):
    if os.getenv('REVIEW_CASE', 'all') not in ('all', 'traversal'):
        continue
    production = source(path)
    # Constructor member initializers contain braces, so slice up to the next method.
    start = production.index('    NodeData::SchlongData::SchlongData(')
    end = production.index('    NiMath::Segment NodeData::SchlongData::GetReferenceSegment()', start)
    run(f'full7_{label}_skeleton', support + production[start:end] + cases)

if os.getenv('REVIEW_CASE', 'all') in ('all', 'direction'):
    code = support + '\nnamespace NiMath {\n' + function(
        source('src/Thread/NiNode/NiMath.cpp'), 'Segment BestFit(') + '\n}\n'
    code += function(source('src/Thread/NiNode/Node.cpp'),
                     'NiMath::Segment NodeData::SchlongData::GetReferenceSegment()')
    code += r'''
NiMath::Segment fit(const std::vector<Vec>& points){
 NodeData::SchlongData chain;
 for(const auto& point:points){auto node=std::make_shared<RE::NiNode>();node->world.translate=point;chain.nodes.push_back(node);}
 return chain.GetReferenceSegment();
}
int main(){
 const Vec base{17,30,-8};
 for(Vec axis:{Vec{1,0,0},Vec{-1,0,0},Vec{0,1,0},Vec{0,-1,0},Vec{0,0,1},Vec{0,0,-1},Vec{1,-2,3},Vec{-3,1,-2}}){
  axis.Unitize();const auto tip=base+axis*20;
  for(int count:{2,3,5,10}){
   std::vector<Vec> points;for(int n=0;n<count;++n)points.push_back(base+axis*(20.f*n/(count-1)));
   auto segment=fit(points);
   assert(segment.first.GetDistance(base)<0.0001f);assert(segment.second.GetDistance(tip)<0.0001f);
   assert(segment.Vector().Dot(tip-base)>0);
  }
 }
 // A folded chain has no unique direction when its endpoints coincide.
 // Keep a finite fit; a near-coincident endpoint still determines its sign.
 for(float tail:{0.f,-0.00001f,0.00001f}){
  const std::vector<Vec> points{{0,0,0},{0,-10,0},{0,tail,0}};auto segment=fit(points);
  assert(std::isfinite(segment.Length()));assert(segment.Vector().Dot(points.back()-points.front())>=0);
 }
 auto collapsed=fit({Vec{3,4,5},Vec{3,4,5},Vec{3,4,5}});
 assert(collapsed.IsPoint()&&collapsed.first==Vec({3,4,5}));
 std::cout<<"PASS: production PCA skeleton segments preserve root-to-tip direction across orientations and degenerate endpoints\n";
}
'''
    run('full7_skeleton_direction', code)
