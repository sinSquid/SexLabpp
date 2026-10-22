from statistics_roundtrip import ROOT, function, run
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>
namespace logger {template<class...T>void error(T&&...) {}}
namespace RE::SEXES {enum SEX {kNone=-1,kMale,kFemale};}
struct Expression {
 enum ValueType {MoodType=30,Total=32};
 enum class Scaling {Linear,Square,Cubic,Exponential};
 int version=0,id=0;Scaling scaling=Scaling::Linear;
 std::vector<std::array<float,Total>> data[2];
 std::array<float,Total> GetData(RE::SEXES::SEX,float)const;
};
'''
code+=function((ROOT/'src/Registry/Define/Expression.cpp').read_text(),'std::array<float, Expression::ValueType::Total> Expression::GetData(')
code+=r'''
int main(){
 Expression e;std::array<float,32> zero{},one;one.fill(1);e.data[0]={zero,one};
 assert(e.GetData(RE::SEXES::kMale,-100)[0]==0);
 assert(e.GetData(RE::SEXES::kMale,10000)[0]==1);
 assert(e.GetData(RE::SEXES::kNone,50)[30]==7);
 assert(e.GetData(RE::SEXES::kMale,std::numeric_limits<float>::quiet_NaN())[0]==0);
 e.version=1;e.scaling=static_cast<Expression::Scaling>(99);
 assert(e.GetData(RE::SEXES::kMale,50)[0]==0.5f);
 for(auto mode:{Expression::Scaling::Square,Expression::Scaling::Cubic,Expression::Scaling::Exponential}){
  e.scaling=mode;auto result=e.GetData(RE::SEXES::kMale,std::numeric_limits<float>::infinity());
  for(auto value:result)assert(std::isfinite(value));
 }
}
'''
if __name__=='__main__':run('expression_sampling',code)
