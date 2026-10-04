"""Sixth-review furniture and paired-anchor regressions with engine stand-ins."""
import os
import subprocess

from source_regressions import ROOT, function, run


def source(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(
            ['git', 'show', f"{os.environ['REVIEW_BASE']}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


support = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <memory>
#include <numbers>
#include <optional>
#include <utility>
#include <vector>
struct Vec {
 float x=0,y=0,z=0;
 Vec()=default;Vec(float a,float b,float c):x(a),y(b),z(c){}
 Vec operator+(Vec b)const{return {x+b.x,y+b.y,z+b.z};}
 Vec operator-(Vec b)const{return {x-b.x,y-b.y,z-b.z};}
 Vec operator*(float s)const{return {x*s,y*s,z*s};}
 Vec& operator+=(Vec b){return *this=*this+b;}
 float Length()const{return std::sqrt(x*x+y*y+z*z);}
 float GetDistance(Vec b)const{return (*this-b).Length();}
};
namespace glm {
 using vec3=Vec;
 struct vec4:Vec {float w;vec4(float a,float b,float c,float d):Vec(a,b,c),w(d){}};
 float distance(vec4 a,vec4 b){return a.GetDistance(b);}
 float degrees(float x){return x*180/std::numbers::pi_v<float>;}
 float radians(float x){return x*std::numbers::pi_v<float>/180;}
}
namespace logger {template<class... T>void error(T&&...){} }
'''


def furniture_test(check_offsets=True):
    furniture = source('src/Registry/Define/Furniture.cpp')
    transform = source('src/Registry/Define/Transform.cpp')
    code = support + r'''
namespace RE {
 enum class FormType {Static,MovableStatic,Furniture,Door};
 struct TESObjectREFR;
 struct NiAVObject {
  NiAVObject* AsNode(){return this;}
  TESObjectREFR* GetUserData(){return nullptr;}
 };
 struct Base {template<class... T>bool Is(T...){return true;}};
 struct TESObjectREFR {
  struct {Vec location;Vec angle;} data;
  NiAVObject node;
  float GetAngleX()const{return data.angle.x;}float GetAngleY()const{return data.angle.y;}
  uint32_t GetFormID()const{return 1;}NiAVObject* Get3D(){return &node;}
  Base* GetBaseObject(){return nullptr;}
 };
}
namespace REX {template<class T>struct EnumSet {bool any(T)const{return true;}};}
namespace Settings {
 float fFurnitureSquare=0,fFurnitureSquareStepSize=8,fFurnitureTiltTolerance=10;
 float fFurnitureSquareHeight=128,fFurnitureSquareFloorSkip=16;
}
struct ObjectBound {
 Vec worldBoundMax{0,0,100};
 Vec GetCenterWorld()const{return {};}
 static std::optional<ObjectBound> MakeBoundingBox(RE::NiAVObject*){return ObjectBound{};}
};
namespace Raycast {
 struct Result {bool hit=false;RE::NiAVObject* hitObject=nullptr;glm::vec4 hitPos{0,0,0,0};};
 std::vector<std::pair<glm::vec4,glm::vec4>> rays;
 bool blocked=false;
 Result hkpCastRay(glm::vec4 start,glm::vec4 end,const std::vector<RE::NiAVObject*>&){
  rays.emplace_back(start,end);return {blocked,nullptr,start};
 }
}
struct Coordinate {
 Vec location;float rotation;
 Coordinate(Vec point,float angle):location(point),rotation(angle){}
 Coordinate(const RE::TESObjectREFR* ref):location(ref->data.location),rotation(ref->data.angle.z){}
 void Apply(Coordinate&)const;Coordinate ApplyReturn(const Coordinate&)const;
 glm::vec4 AsVec4(float w)const{return {location.x,location.y,location.z,w};}
};
struct FurnitureType {enum Value {Chair};Value value=Chair;};
using FurnitureOffset=std::pair<FurnitureType,Coordinate>;
struct FurnitureDetails {
 std::vector<FurnitureOffset> data;
 std::vector<FurnitureOffset> GetCoordinatesInBound(RE::TESObjectREFR*,REX::EnumSet<FurnitureType::Value>)const;
};
'''
    for signature in ('void Coordinate::Apply(', 'Coordinate Coordinate::ApplyReturn('):
        code += function(transform, signature) + '\n'
    code += function(furniture, 'uint32_t FurnitureScanSteps(') + '\n'
    code += function(furniture, 'std::vector<FurnitureOffset> FurnitureDetails::GetCoordinatesInBound(')
    code += r'''
bool close(float a,float b){return std::abs(a-b)<0.0001f;}
int main(){
 RE::TESObjectREFR ref;ref.data.location={100,200,30};ref.data.angle.z=std::numbers::pi_v<float>/2;
 FurnitureDetails details;details.data.emplace_back(FurnitureType{},Coordinate{{0,10,2},0});
 if(CHECK_OFFSETS){
 auto valid=details.GetCoordinatesInBound(&ref,{});assert(valid.size()==1);assert(Raycast::rays.size()==1);
 auto [start,end]=Raycast::rays.back();
 // Local +Y rotates to world +X. Ray tests must use the same point as actor placement.
 assert(close(start.x,110)&&close(start.y,200)&&close(start.z,48));
 assert(close(end.x,110)&&close(end.y,200)&&close(end.z,160));
 details.data.front().second.rotation=std::numbers::pi_v<float>/3;
 Raycast::rays.clear();details.GetCoordinatesInBound(&ref,{});
 assert(close(Raycast::rays.back().first.x,110)&&close(Raycast::rays.back().first.y,200));
 Raycast::blocked=true;assert(details.GetCoordinatesInBound(&ref,{}).empty());Raycast::blocked=false;
 }
 // Tilt tolerance is configured in degrees; signs and equivalent full turns agree.
 for(float degrees:{-180.f,-11.f,11.f,180.f,349.f,371.f})for(int axis:{0,1}){
  ref.data.angle.x=axis==0?glm::radians(degrees):0;
  ref.data.angle.y=axis==1?glm::radians(degrees):0;
  Raycast::rays.clear();assert(details.GetCoordinatesInBound(&ref,{}).empty());assert(Raycast::rays.empty());
 }
 for(float degrees:{-10.f,-9.f,0.f,9.f,10.f,351.f,360.f,369.f}){
  ref.data.angle.x=glm::radians(degrees);ref.data.angle.y=0;
  assert(details.GetCoordinatesInBound(&ref,{}).size()==1);
 }
 ref.data.angle.x=std::numeric_limits<float>::quiet_NaN();assert(details.GetCoordinatesInBound(&ref,{}).empty());
 std::cout<<"PASS: furniture rays apply local offsets in world space; signed/periodic/nonfinite tilt is filtered in degrees\n";
}
'''
    run('full6_furniture', code.replace('CHECK_OFFSETS', str(check_offsets).lower()))


def paired_anchor_test():
    production = source('src/Thread/NiNode/NiInteraction.cpp')
    code = support + r'''
namespace RE {using NiPoint3=Vec;}
namespace NiMath {
 struct Segment {
  Vec first,second;Vec Vector()const{return second-first;}
  float Length()const{return Vector().Length();}
  Segment ShortestSegmentTo(Vec p)const{return {p,first};}
 };
 void EnsureAntiParallelDirection(Vec&,Vec){}
 float GetAngleCos(Vec,Vec){return 0;}
}
struct MotionDescriptor {
 NiMath::Segment trajectory{{0,0,0},{1,0,0}};float avgSpeed=1;
 bool DescribesMotion()const{return true;}
};
struct Bound {
 Vec boundMax{10,10,10};
 bool IsValid()const{return true;}
 bool IsPointInside(Vec p)const{return p.GetDistance({100,200,30})<=1;}
};
struct NiMotion {
 enum Anchor {pHead,pSchlongBase,pSchlongTip,pMouth,pPelvis,vHeadY,vHeadX,vHeadZ};
 std::array<Vec,8> points{};
 bool HasSufficientData()const{return true;}bool HasMomentData(Anchor)const{return true;}
 Bound GetLatestHeadBound()const{return {};}
 MotionDescriptor DescribeMotion(Anchor)const{return {};}
 Vec GetLatestMoment(Anchor a)const{return points[a];}
};
namespace Settings {
 float fCloseToHeadRatio=1,fVeryCloseToHeadRatio=0.5f,fMinSpeedPenetration=1;
}
namespace NiType {enum class Type{Oral,Deepthroat,Skullfuck,LickingShaft,Head_NONE};}
struct INiDescriptor {
 enum class Feature{Angle01,Angle02,Angle03,Distance01,Distance02,Distance03,Distance04,Velocity01};
 std::array<float,8> values{};
 virtual ~INiDescriptor()=default;
 void AddValue(Feature feature,float value){values[static_cast<size_t>(feature)]=value;}
};
template<NiType::Type>struct NiDescriptor:INiDescriptor{};
struct Interaction {std::unique_ptr<INiDescriptor> descriptor;float velocity;};
struct NiInteractionCluster{std::vector<Interaction> interactions;};
template<class T>void AddBasicPairedScores01(T*,const MotionDescriptor&,const MotionDescriptor&){}
'''
    code += function(production, 'NiInteractionCluster EvaluateHeadInteractions(')
    code += r'''
int main(){
 NiMotion receiving,penetrating;
 receiving.points[NiMotion::pHead]={100,200,30};receiving.points[NiMotion::pMouth]={100,200,30};
 receiving.points[NiMotion::pPelvis]={100,200,-30};
 penetrating.points[NiMotion::pSchlongBase]={100,200,30};
 penetrating.points[NiMotion::pSchlongTip]={100,200,35};
 penetrating.points[NiMotion::pPelvis]={100,200,30};
 auto cluster=EvaluateHeadInteractions(receiving,penetrating);assert(cluster.interactions.size()==5);
 auto distance=cluster.interactions[1].descriptor->values[static_cast<size_t>(INiDescriptor::Feature::Distance04)];
 assert(std::abs(distance-0.02f)<0.00001f);
 // Moving only the receiving actor's pelvis inside must not fake partner penetration.
 receiving.points[NiMotion::pPelvis]={100,200,30};penetrating.points[NiMotion::pPelvis]={100,200,-30};
 cluster=EvaluateHeadInteractions(receiving,penetrating);
 distance=cluster.interactions[1].descriptor->values[static_cast<size_t>(INiDescriptor::Feature::Distance04)];
 assert(std::abs(distance-1.f)<0.00001f);
 std::cout<<"PASS: head interaction depth feature uses the penetrating partner's pelvis\n";
}
'''
    run('full6_paired_anchor', code)


if os.getenv('REVIEW_CASE', 'all') in ('all', 'furniture'):
    furniture_test()
if os.getenv('REVIEW_CASE') == 'tilt':
    furniture_test(check_offsets=False)
if os.getenv('REVIEW_CASE', 'all') in ('all', 'paired_anchor'):
    paired_anchor_test()
