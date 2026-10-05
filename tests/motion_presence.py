"""Actual NiMotion class, methods and PCA with vector/node stand-ins; no game ABI."""
import ast
from source_regressions import ROOT, function, run
import os, subprocess
def production(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
    return (ROOT/path).read_text()
# Reuse only the vector/matrix stand-ins, without importing/running that test.
tree=ast.parse((ROOT/'tests/full_seventh_geometry.py').read_text())
support=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='support' for t in n.targets))
support=support[:support.index('struct NodeData {')]
support=support.replace('SEGMENT_DEFINITION',function(production('src/Thread/NiNode/NiMath.h'),'struct Segment :')+';')
support=support.replace('Vec operator-(Vec b)const', 'Vec operator/(float s)const{return *this*(1/s);}\n Vec operator-(Vec b)const')
support=support.replace('Vec GetVectorY()const', 'Vec GetVectorX()const{return {1,0,0};}\n Vec GetVectorZ()const{return {0,0,1};}\n Vec GetVectorY()const')
support+='''
#include <bitset>
#include <functional>
#include <optional>
#include <limits>
namespace logger {template<class...T>void warn(T&&...){} }
namespace magic_enum {template<class T>constexpr size_t enum_count(){return 15;}}
struct ObjectBound {
 Vec boundMin{-1,-1,-1},boundMax{1,1,1};
 static std::optional<ObjectBound> MakeBoundingBox(RE::NiNode*){return ObjectBound{};}
};
namespace Thread::NiNode::Node {
 struct NodeData {
  RE::NiPointer<RE::NiNode> head,clitoris;
  struct Schlong {NiMath::Segment GetReferenceSegment()const{return {{},{0,1,0}};}};
  std::vector<std::shared_ptr<Schlong>> schlongs;
  std::optional<NiMath::Segment> GetVaginalSegment()const{return {};}
  std::optional<NiMath::Segment> GetAnalSegment()const{return {};}
  NiMath::Segment GetCrotchSegment()const{return {{},{0,1,0}};}
 };
}
'''
header=production('src/Thread/NiNode/NiMotion.h')
header='\n'.join(line for line in header.splitlines() if not line.startswith(('#include','#pragma')))
code=support+header+'\n'+production('src/Thread/NiNode/NiMotion.cpp').replace('#include "NiMotion.h"','')
code+='\nnamespace NiMath {\n'+function(production('src/Thread/NiNode/NiMath.cpp'),'Segment BestFit(')+'\n}\n'
code+=r'''
int main(){
 using namespace Thread::NiNode;
 Node::NodeData nodes;nodes.head=std::make_shared<RE::NiNode>();
 NiMotion motion(6,3);
 motion.Push(nodes,0);assert(motion.HasMomentData(NiMotion::pHead)); // World origin is present.
 assert(!motion.HasMomentData(NiMotion::pClitoris));
 for(int i=1;i<4;++i){nodes.head->world.translate={float(i),0,0};motion.Push(nodes,float(i));}
 auto d=motion.DescribeMotion(NiMotion::pHead);assert(d.totalDistance==3&&d.duration==3&&d.avgSpeed==1);
 // Losing a node breaks the history; its zero placeholder is never a sample.
 nodes.head.reset();motion.Push(nodes,4);assert(!motion.HasMomentData(NiMotion::pHead));
 assert(motion.DescribeMotion(NiMotion::pHead).totalDistance==0);
 nodes.head=std::make_shared<RE::NiNode>();nodes.head->world.translate={100,0,0};motion.Push(nodes,5);
 assert(motion.HasMomentData(NiMotion::pHead));assert(motion.DescribeMotion(NiMotion::pHead).duration==0);
 for(int i=1;i<4;++i){nodes.head->world.translate={100.f+i,0,0};motion.Push(nodes,5.f+i);}
 d=motion.DescribeMotion(NiMotion::pHead);assert(d.totalDistance==3&&d.duration==3&&d.avgSpeed==1);
 int visited=0;motion.ForEachMoment(NiMotion::pHead,[&](Vec p,float){assert(p.x>=100);++visited;return false;});assert(visited==4);
 nodes.head->world.translate.x=std::numeric_limits<float>::quiet_NaN();motion.Push(nodes,9);
 assert(!motion.HasMomentData(NiMotion::pHead));assert(motion.DescribeMotion(NiMotion::pHead).totalDistance==0);
 nodes.head->world.translate={};motion.Push(nodes,std::numeric_limits<float>::infinity());assert(!motion.HasMomentData(NiMotion::pHead));
 // Ring overwrite drops the gap and returns to the allocation-free full-window PCA path.
 for(int i=0;i<8;++i){nodes.head->world.translate={float(i),0,0};motion.Push(nodes,float(i));}
 d=motion.DescribeMotion(NiMotion::pHead);assert(d.totalDistance==5&&d.duration==5&&d.avgSpeed==1);
 NiMotion minimum(0,3);minimum.Push(nodes,0);assert(minimum.Capacity()==1&&minimum.HasMomentData(NiMotion::pHead));
 std::cout<<"PASS: actual motion/PCA distinguishes origin, missing/nonfinite samples and contiguous ring histories\n";
}
'''
run('motion_presence',code)
