from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/NiNode/NiDescriptor.h').read_text()
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <format>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>
namespace NiType {
enum class Type{Vaginal,Anal};enum class Cluster{Crotch};
std::vector<Type> GetTypesForCluster(Cluster){return {Type::Vaginal,Type::Anal};}
}
namespace magic_enum {
std::string_view enum_name(NiType::Type type){return type==NiType::Type::Vaginal?"Vaginal":"Anal";}
template<class T>auto enum_names(){return std::array<std::string_view,2>{"Distance01","Time01"};}
}
struct INiDescriptor {
 enum class Feature{Distance01,Time01};static constexpr size_t NUM_FEATURES=2;
 NiType::Type type;
 NiType::Type GetType()const{return type;}
 std::string CsvRow()const{return std::string(magic_enum::enum_name(type))+",1,2,3";}
'''
for signature in ('static std::string CreateCsvHeader(', 'static std::string CreateCsvRow('):
 code+=function(source,signature)+'\n'
code+=r'''
};
int main(){
 INiDescriptor a{NiType::Type::Vaginal},b{NiType::Type::Anal};
 auto header=INiDescriptor::CreateCsvHeader(NiType::Cluster::Crotch);
 assert(header=="Id_Vaginal,Vaginal_Distance01,Vaginal_Time01,Vaginal_Prediction,Id_Anal,Anal_Distance01,Anal_Time01,Anal_Prediction");
 auto full=INiDescriptor::CreateCsvRow({&b,&a},NiType::Cluster::Crotch);
 auto missing=INiDescriptor::CreateCsvRow({&b},NiType::Cluster::Crotch);
 auto empty=INiDescriptor::CreateCsvRow({},NiType::Cluster::Crotch);
 assert(full=="Vaginal,1,2,3,Anal,1,2,3");
 assert(missing=="Vaginal,0,0,0,Anal,1,2,3");
 for(const auto& row:{full,missing,empty})assert(std::count(row.begin(),row.end(),',')==std::count(header.begin(),header.end(),','));
 std::cout<<"PASS: production CSV schema remains fixed across reordered/missing/empty descriptors\n";
}
'''
run('csv_schema',code)
