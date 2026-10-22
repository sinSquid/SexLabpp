from statistics_roundtrip import ROOT, function, run

code=r'''
#include <cassert>
#include <mutex>
#include <string>
#include <thread>
#include <utility>
#include <vector>
struct Settings {
 static inline std::recursive_mutex saveMutex;
'''
source=(ROOT/'src/UserData/Settings.h').read_text()
for signature in ('static T ReadMCM(', 'static void WriteMCM('):
    code+='template<class T> '+function(source,signature)+'\n'
code+=r'''
};
int main(){
 std::string text(1024,'A');std::vector<int> values(16,1);
 std::vector<std::thread> workers;
 for(int n=0;n<4;++n)workers.emplace_back([&,n](){
  for(int i=0;i<2000;++i){
   Settings::WriteMCM(text,std::string(1024,static_cast<char>('A'+n)));
   auto copy=Settings::ReadMCM(text);assert(copy.size()==1024&&copy.find_first_not_of(copy[0])==std::string::npos);
   Settings::WriteMCM(values,std::vector<int>(16,n));auto v=Settings::ReadMCM(values);
   for(auto item:v)assert(item==v[0]);
  }
 });
 for(auto& w:workers)w.join();
}
'''
if __name__=='__main__': run('settings_access',code)
