"""Actual GetData arithmetic; profile/logger stand-ins, not a VM or SDK test."""
import os
import subprocess
from source_regressions import ROOT, function, run

path = 'src/Registry/Define/Expression.cpp'
source = (subprocess.check_output(['git', 'show', os.environ['REVIEW_BASE'] + ':' + path], cwd=ROOT, text=True)
          if os.getenv('REVIEW_BASE') else (ROOT/path).read_text())
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <limits>
#include <vector>
namespace RE {namespace SEXES {enum SEX {kMale, kFemale, kTotal};}}
namespace logger {template<class...T> void error(T&&...) {}}
namespace Registry {
struct Expression {
 enum ValueType {MoodType=30, Total=32};
 enum class Scaling {Linear, Square, Cubic, Exponential};
 int version=1, id=1;
 Scaling scaling=Scaling::Linear;
 std::vector<std::array<float, Total>> data[2];
 std::array<float, Total> GetData(RE::SEXES::SEX, float) const;
};
''' + function(source, 'std::array<float, Expression::ValueType::Total> Expression::GetData(') + r'''
}
int main() {
 Registry::Expression e;
 std::array<float,32> low{}, high{};
 const float limit=std::numeric_limits<float>::max();
 low.fill(-limit);high.fill(limit);e.data[0]={low,high};
 auto middle=e.GetData(RE::SEXES::kMale,50);
 for(float value:middle) assert(std::isfinite(value)&&value==0);
 for(float strength:{0.f,100.f,125.f,-limit,limit}) {
  const auto values=e.GetData(RE::SEXES::kMale,strength);
  for(float value:values) assert(std::isfinite(value));
 }
 auto start=e.GetData(RE::SEXES::kMale,0);auto end=e.GetData(RE::SEXES::kMale,100);
 assert(start[0]==-limit&&end[0]==limit);
 for(auto scaling:{Registry::Expression::Scaling::Linear,Registry::Expression::Scaling::Square,
                   Registry::Expression::Scaling::Cubic,Registry::Expression::Scaling::Exponential}) {
  e.scaling=scaling;
  for(float value:e.GetData(RE::SEXES::kMale,limit)) assert(std::isfinite(value));
 }
 // Ordinary interpolation/extrapolation and discrete mood rounding remain intact.
 e.scaling=Registry::Expression::Scaling::Linear;
 low.fill(.2f);high.fill(.8f);low[30]=2;high[30]=9;e.data[0]={low,high};
 assert(std::abs(e.GetData(RE::SEXES::kMale,50)[0]-.5f)<1e-6f);
 assert(e.GetData(RE::SEXES::kMale,50)[30]==6);
 assert(std::abs(e.GetData(RE::SEXES::kMale,125)[0]-.95f)<1e-6f);
 assert(std::abs(e.GetData(RE::SEXES::kMale,-50)[0]+.1f)<1e-6f);
 e.version=0;assert(e.GetData(RE::SEXES::kMale,100)==high);
}
'''
run('expression_numeric_range', code)
print('PASS: actual expression interpolation stays finite for finite extreme profiles and preserves ordinary results')
