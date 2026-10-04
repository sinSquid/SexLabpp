"""Second full-review numerical and data-loading regressions (engine stand-ins)."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

from source_regressions import ROOT, function, run


def source(path):
    # Optional baseline is useful to demonstrate that a regression fails before a fix.
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git', 'show', f"{os.environ['REVIEW_BASE']}:{path}"], cwd=ROOT, text=True)
    return (ROOT / path).read_text()


support = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cfloat>
#include <cmath>
#include <iostream>
#include <limits>
#include <optional>
#include <random>
#include <span>
#include <vector>
namespace std {using ::sinf;using ::cosf;using ::acosf;}
struct Vec {
 float x=0,y=0,z=0;
 Vec()=default;Vec(float a):x(a),y(a),z(a){}Vec(float a,float b,float c):x(a),y(b),z(c){}
 float& operator[](size_t i){return i==0?x:i==1?y:z;}
 float operator[](size_t i)const{return i==0?x:i==1?y:z;}
 Vec operator+(Vec b)const{return {x+b.x,y+b.y,z+b.z};}
 Vec operator-(Vec b)const{return {x-b.x,y-b.y,z-b.z};}
 Vec operator-()const{return {-x,-y,-z};}
 Vec operator*(float t)const{return {x*t,y*t,z*t};}
 Vec operator/(float t)const{return *this*(1/t);}
 Vec& operator+=(Vec b){return *this=*this+b;}
 Vec& operator/=(float t){return *this=*this/t;}
 float Dot(Vec b)const{return x*b.x+y*b.y+z*b.z;}
 Vec Cross(Vec b)const{return {y*b.z-z*b.y,z*b.x-x*b.z,x*b.y-y*b.x};}
 float SqrLength()const{return Dot(*this);}
 float Length()const{return std::sqrt(SqrLength());}
 void Unitize(){auto n=Length();if(n>0)*this/=n;}
 static Vec Zero(){return {};}
};
Vec operator*(float n,Vec v){return v*n;}
struct Matrix {
 float entry[3][3]={{1,0,0},{0,1,0},{0,0,1}};
 Matrix()=default;
 Matrix(Vec a,Vec b,Vec c){for(int i=0;i<3;++i){entry[0][i]=a[i];entry[1][i]=b[i];entry[2][i]=c[i];}}
 Vec operator*(Vec v)const{Vec r;for(int i=0;i<3;++i)for(int j=0;j<3;++j)r[i]+=entry[i][j]*v[j];return r;}
 Matrix operator*(float x)const{auto r=*this;for(auto& row:r.entry)for(auto& v:row)v*=x;return r;}
 Matrix operator+(const Matrix& b)const{auto r=*this;for(int i=0;i<3;++i)for(int j=0;j<3;++j)r.entry[i][j]+=b.entry[i][j];return r;}
 Matrix operator*(const Matrix& b)const{auto r=*this*0;for(int i=0;i<3;++i)for(int j=0;j<3;++j)for(int k=0;k<3;++k)r.entry[i][j]+=entry[i][k]*b.entry[k][j];return r;}
 // GLM indexes matrices by column.
 Vec operator[](size_t j)const{return {entry[0][j],entry[1][j],entry[2][j]};}
};
namespace RE {using NiPoint3=Vec;using NiMatrix3=Matrix;struct NiNode {};}
struct Segment {Vec first,second;Vec Vector()const{return second-first;}};
namespace glm {
 using vec3=Vec;using mat3=Matrix;
 float dot(Vec a,Vec b){return a.Dot(b);}Vec cross(Vec a,Vec b){return a.Cross(b);}
 float length(Vec v){return v.Length();}Vec normalize(Vec v){v.Unitize();return v;}
 Matrix transpose(Matrix m){auto r=m;for(int i=0;i<3;++i)for(int j=0;j<3;++j)r.entry[i][j]=m.entry[j][i];return r;}
 Matrix eulerAngleXYZ(float x,float y,float z){
  Matrix rx{{1,0,0},{0,std::cos(x),-std::sin(x)},{0,std::sin(x),std::cos(x)}};
  Matrix ry{{std::cos(y),0,std::sin(y)},{0,1,0},{-std::sin(y),0,std::cos(y)}};
  Matrix rz{{std::cos(z),-std::sin(z),0},{std::sin(z),std::cos(z),0},{0,0,1}};
  return rx*ry*rz;
 }
}
'''
math = source('src/Thread/NiNode/NiMath.cpp')
code = support
for sig in ('Segment BestFit(', 'RE::NiMatrix3 RotateTowards(', 'float GetAngleCos(', 'float GetAngle(',
            'inline RE::NiPoint3 ProjectToXY(', 'inline RE::NiPoint3 ProjectToXZ(', 'inline RE::NiPoint3 ProjectToYZ(',
            'float GetAngleXY(const RE::NiPoint3&', 'float GetAngleXZ(const RE::NiPoint3&', 'float GetAngleYZ(const RE::NiPoint3&'):
    code += function(math, sig) + '\n'
code += r'''
int main(){
 // Each line is perpendicular to the old (1,1,1) seed.
 for(Vec d:{Vec{1,-1,0},Vec{0,1,-1},Vec{-1,0,1}})for(float scale:{1.f,0.00001f}){
  d=d*scale;std::array p{d*-2,d,d*3};auto fit=BestFit(p);
  assert(fit.Vector().Length()>d.Length()*4.99f);
  assert(fit.Vector().Cross(d).Length()<d.SqrLength()*0.001f);
 }
 std::array<Vec,4> stationary{Vec{2,3,4},Vec{2,3,4},Vec{2,3,4},Vec{2,3,4}};
 assert(BestFit(stationary).Vector().SqrLength()==0);
 // Dominant Y variation must win even though the X seed is an eigenvector.
 std::array<Vec,4> scatter{Vec{1,0,0},Vec{-1,0,0},Vec{0,4,0},Vec{0,-4,0}};
 assert(std::abs(BestFit(scatter).Vector().y)>7.99f);
 for(float magnitude:{0.00001f,1.f,1000.f}){
  Vec v{magnitude,0,0};auto turned=RotateTowards(v,-v,0.2f)*v;
  assert(std::abs(std::atan2(turned.y,turned.x)-0.2f)<1e-5f);
  assert((RotateTowards(v,-v,0)*v+v).Length()<magnitude*1e-5f);
  assert((RotateTowards(v,-v,-0.2f)*v-v).Length()<magnitude*1e-5f);
 }
 assert(std::abs(GetAngleXY({1,0,8},{0,1,-4})-1.5707963f)<1e-5f);
 assert(std::abs(GetAngleXZ({1,8,0},{0,-4,1})-1.5707963f)<1e-5f);
 assert(std::abs(GetAngleYZ({8,1,0},{-4,0,1})-1.5707963f)<1e-5f);
 assert(GetAngleXY({0,0,1},{1,0,0})==0);
 std::cout<<"PASS: PCA orthogonal seeds/tiny motions/dominant axis, limited antiparallel rotation and projected radians\n";
}
'''
run('full2_math', code)

bound = source('src/Registry/Util/RayCast/ObjectBound.cpp')
code = support + r'''
struct ObjectBound {
 Vec boundMin,boundMax,worldBoundMin,worldBoundMax,rotation;
 Vec GetCenterWorld()const;
 bool IsPointInside(float,float,float)const;
 bool IsValid()const;
 static std::optional<ObjectBound> MakeBoundingBox(RE::NiNode*){return {};}
};
'''
for sig in ('glm::vec3 ObjectBound::GetCenterWorld(', 'bool ObjectBound::IsPointInside(float', 'bool ObjectBound::IsValid('):
    code += function(bound, sig) + '\n'
sat = source('src/Registry/Util/SAT.h')
code += '\n'.join(line for line in sat.splitlines() if not line.startswith(('#include', '#pragma'))) + r'''
ObjectBound box(Vec center,Vec half,Vec rotation={}){
 auto m=glm::mat3(glm::eulerAngleXYZ(rotation.x,rotation.y,rotation.z));
 return {-half,half,center-m*half,center+m*half,rotation};
}
int main(){
 const Vec center{-20,-30,-40};
 std::mt19937 rng(73);std::uniform_real_distribution<float> angle(-3,3);
 for(int n=0;n<200;++n){
  Vec rotation{angle(rng),angle(rng),angle(rng)};auto b=box(center,{1,2,3},rotation);
  auto m=glm::mat3(glm::eulerAngleXYZ(rotation.x,rotation.y,rotation.z));
  for(auto local:{Vec{0,0,0},Vec{0.9f,1.9f,2.9f}}){auto p=center+m*local;assert(b.IsPointInside(p.x,p.y,p.z));}
  auto outside=center+m*Vec{1.1f,0,0};assert(!b.IsPointInside(outside.x,outside.y,outside.z));
  SAT::OrientedObjectBound obb(nullptr,b);auto corners=obb.GetCorners();
  for(auto p:corners){auto local=glm::transpose(m)*(p-center);assert(std::abs(std::abs(local.x)-1)<1e-4f);assert(std::abs(std::abs(local.y)-2)<1e-4f);assert(std::abs(std::abs(local.z)-3)<1e-4f);}
  SAT::OrientedObjectBound far(nullptr,box(center+m*Vec{4,0,0},{1,2,3},rotation));
  assert(!SAT::SAT(obb,far));
  SAT::OrientedObjectBound close(nullptr,box(center+m*Vec{1.5f,0,0},{1,2,3},rotation));
  auto hit=SAT::SAT(obb,close);assert(hit&&std::abs(hit->mtv-0.5f)<1e-4f);
 }
 SAT::OrientedObjectBound outer(nullptr,box(center,{3,3,3})),inner(nullptr,box(center,{1,1,1}));
 auto contained=SAT::SAT(outer,inner);assert(contained&&std::abs(contained->mtv-4)<1e-5f);
 auto displaced=box(center+contained->mtv_axis*(contained->mtv+0.01f),{3,3,3});
 assert(!SAT::SAT(SAT::OrientedObjectBound(nullptr,displaced),inner));
 assert(!ObjectBound{}.IsPointInside(0,0,0));
 std::cout<<"PASS: 200 rotated negative-coordinate bounds, SAT separation/penetration/containment and corners\n";
}
'''
run('full2_bounds', code)

spec = importlib.util.spec_from_file_location('load_data', ROOT / 'scripts/ML/load_data.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    cluster = root / 'SKSE/SexLab/ModelData/Test'
    cluster.mkdir(parents=True)
    (cluster / 'a.csv').write_text('Label,A_X\n0,1\n')
    (cluster / 'b.csv').write_text('A_X,Label\n2,1\n')
    result = module.load_data(str(root))['Test']
    assert result['A_X'].tolist() == [1, 2]
    (cluster / 'b.csv').write_text('Label,A_Y\n0,1\n')
    try:
        module.load_data(str(root))
    except ValueError as error:
        assert 'across files' in str(error)
    else:
        raise AssertionError('Mismatched CSV files silently merged into NaN features')
print('PASS: cross-file CSV schema validation accepts reordered columns and rejects missing/extra fields')

# Source contracts, not Havok or xmake execution.
bound = source('src/Registry/Util/RayCast/ObjectBound.cpp')
assert 'rigidBodyLocalTranslation.quad = _mm_setzero_ps();' in bound
assert '_mm_store_ps(' not in bound
lua = source('xmake/papyrus/papyrus.lua')
assert lua.index('target:add("installfiles", sourcefiles') < lua.index('for _, v in ipairs(sourcefiles) do')
print('PASS: source contracts for initialized Havok translation, unaligned stores and linear install registration')

from unittest.mock import patch
spec = importlib.util.spec_from_file_location('audio_convert', ROOT / 'dist/Sound/fx/SexLab/vfx/ConvertMp3ToWav.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)
with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    mp3, wav = root / 'voice.mp3', root / 'voice.wav'
    mp3.write_bytes(b'source audio')

    def failed(args, **kwargs):
        Path(args[-1]).write_bytes(b'partial')
        if kwargs.get('check'):
            raise subprocess.CalledProcessError(1, args)
        return subprocess.CompletedProcess(args, 1)

    with patch.object(audio.subprocess, 'run', failed):
        try:
            audio.convert_mp3_to_wav(root)
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError('failed converter was ignored')
    assert mp3.read_bytes() == b'source audio' and not wav.exists()
    assert sorted(p.name for p in root.iterdir()) == ['voice.mp3']
    wav.write_bytes(b'existing')
    with patch.object(audio.subprocess, 'run') as invoke:
        audio.convert_mp3_to_wav(root)
        invoke.assert_not_called()
    assert mp3.exists() and wav.read_bytes() == b'existing'
    wav.unlink()

    def succeeded(args, **kwargs):
        assert kwargs['check'] is True
        Path(args[-1]).write_bytes(b'complete audio')

    with patch.object(audio.subprocess, 'run', succeeded):
        audio.convert_mp3_to_wav(root)
    assert not mp3.exists() and wav.read_bytes() == b'complete audio'
print('PASS: audio conversion preserves source on failure/existing output and publishes completed output before deletion')
