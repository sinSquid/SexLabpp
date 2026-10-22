from statistics_roundtrip import ROOT, run
code=r'''
#include <cassert>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
namespace RE {using BSFixedString=std::string;}
#include "Registry/Util/Decode.h"
void write(const std::filesystem::path& p,const std::string& bytes){std::ofstream f(p,std::ios::binary);f.write(bytes.data(),bytes.size());}
std::string prefix(uint64_t n){std::string out(8,'\0');for(int i=7;i>=0;--i){out[i]=static_cast<char>(n&255);n>>=8;}return out;}
int main(int argc,char**argv){
 assert(argc==2);std::filesystem::path file=std::string(argv[1])+".bin";
 write(file,prefix(3)+"abc"+prefix(0));
 {std::ifstream stream(file,std::ios::binary);Decode::InputBounds bounds(stream);std::string value;
 Decode::Read(stream,value);assert(value=="abc");Decode::Read(stream,value);assert(value.empty()&&Decode::Remaining(stream)==0);}
 write(file,prefix(UINT64_MAX));
 {std::ifstream stream(file,std::ios::binary);std::string value="keep";bool failed=false;try{Decode::Read(stream,value);}catch(const std::runtime_error&){failed=true;}assert(failed&&value=="keep");}
 write(file,std::string(1,'X'));
 {std::ifstream stream(file,std::ios::binary);int32_t value=123;bool failed=false;try{Decode::Read(stream,value);}catch(const std::runtime_error&){failed=true;}assert(failed&&value==123);}
 write(file,std::string(4,static_cast<char>(255)));
 {std::ifstream stream(file,std::ios::binary);int32_t value=0;Decode::Read(stream,value);assert(value==-1);}
 write(file,prefix(0x8000000000000000ULL));
 {std::ifstream stream(file,std::ios::binary);uint64_t value=0;Decode::Read(stream,value);assert(value==0x8000000000000000ULL);}
 write(file,"abcd");
 {std::ifstream stream(file,std::ios::binary);assert(stream.pword(Decode::InputBounds::Slot())==nullptr);
 {Decode::InputBounds outer(stream);assert(Decode::Remaining(stream)==4);{Decode::InputBounds nested(stream);assert(Decode::Remaining(stream)==4);}}
 assert(stream.pword(Decode::InputBounds::Slot())==nullptr);}
}
'''
if __name__=='__main__':run('decode_bounds',code)
