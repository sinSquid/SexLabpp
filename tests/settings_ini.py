from statistics_roundtrip import ROOT, function, run
code=r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <limits>
#include <map>
#include <string>
#include <type_traits>
namespace fs {bool exists(const char*){return true;}}
namespace logger {template<class...T>void error(T&&...){}template<class...T>void info(T&&...) {}}
constexpr const char* INIPATH="unused.ini";
struct CSimpleIniA {
 static inline std::map<std::string,double> values;
 void SetUnicode(){}int LoadFile(const char*){return 0;}
 const char* GetValue(const char*,const char* key){return values.contains(key)?"set":nullptr;}
 long GetLongValue(const char*,const char* key){return static_cast<long>(values.at(key));}
 double GetDoubleValue(const char*,const char* key){return values.at(key);}
};
struct Settings {
 static void InitializeINI();
#define INI_SETTING(NAME, DEFAULT, CATEGORY) static inline decltype(DEFAULT) NAME=DEFAULT;
#include "UserData/config.def"
#undef INI_SETTING
};
'''
code+=function((ROOT/'src/UserData/Settings.cpp').read_text(),'void Settings::InitializeINI()').replace('"config.def"','"UserData/config.def"')
code+=r'''
int main(){
 for(double invalid:{-1.0,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
  CSimpleIniA::values={{"fPercentageHetero",invalid},{"fPercentageHomo",invalid},{"fFurnitureSquareStepSize",invalid},{"fFurnitureSquare",invalid}};
  Settings::InitializeINI();assert(Settings::fPercentageHetero==80&&Settings::fPercentageHomo==9);
  assert(Settings::fFurnitureSquareStepSize==8&&Settings::fFurnitureSquare==32);
 }
 CSimpleIniA::values={{"fPercentageHetero",std::numeric_limits<float>::max()},{"fPercentageHomo",std::numeric_limits<float>::max()},{"fFurnitureSquareStepSize",0}};
 Settings::InitializeINI();assert(Settings::fPercentageHetero==50&&Settings::fPercentageHomo==50&&Settings::fFurnitureSquareStepSize==8);
 CSimpleIniA::values={{"fPercentageHetero",80},{"fPercentageHomo",9},{"fFurnitureSquareStepSize",4}};
 Settings::InitializeINI();assert(Settings::fPercentageHetero==80&&Settings::fPercentageHomo==9&&Settings::fFurnitureSquareStepSize==4);
}
'''
if __name__=='__main__':run('settings_ini',code)
