"""Real GLM matrix conversion; no Havok or game ABI simulation."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
from fork_review_regressions import ROOT

cache=(ROOT/'.xmake/windows/x64/cache/package').read_text()
include=re.search(r'\[\[([^\n]*\\glm\\[^\n]*\\include)\]\]',cache)[1]
if os.name != 'nt':include='/mnt/'+include[0].lower()+include[2:].replace('\\','/')
code=r'''
#include <cassert>
#include <cmath>
namespace RE {struct NiMatrix3 {float entry[3][3];};}
#include "Registry/Util/RayCast/Math.h"
int main(){
 for(int n=0;n<100;++n){
  auto expected=glm::eulerAngleXYZ(n*.003f,n*.002f,n*.011f);
  RE::NiMatrix3 input{};
  for(int r=0;r<3;++r)for(int c=0;c<3;++c)input.entry[r][c]=expected[c][r];
  const auto angles=Misc::Math::RotMatrixToEuler(input);
  const auto actual=glm::eulerAngleXYZ(angles.x,angles.y,angles.z);
  for(int r=0;r<3;++r)for(int c=0;c<3;++c)assert(std::abs(actual[c][r]-expected[c][r])<.0001f);
 }
}
'''
with tempfile.TemporaryDirectory() as directory:
    source=Path(directory)/'test.cpp'; binary=Path(directory)/'test'
    source.write_text(code)
    subprocess.run([os.getenv('CXX','g++'),'-std=c++23','-I',str(ROOT/'src'),'-isystem',include,str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
print('PASS: real GLM rotation conversion identity and 99 rotated matrices')
