"""Production tracking serialization and concurrency regressions."""
from pathlib import Path
import tempfile
from fork_review_regressions import ROOT, run as compile_run

def run(name, code):
    with tempfile.TemporaryDirectory() as tmp:
        compile_run(name, code, Path(tmp))

header=(ROOT/'src/Papyrus/sslLibrary/Serialize.h').read_text().replace('#pragma once','')
code=r'''
#include <map>
#include <vector>
#include <string>
#include <mutex>
#include <thread>
#include <algorithm>
#include <cassert>
#include <cstring>
#include <cstdint>
#include <iostream>
namespace RE {using FormID=uint32_t;using BSFixedString=std::string;}
template<class T>struct Singleton {};
namespace logger{template<class... T>void info(T&&...){} template<class... T>void error(T&&...){} }
namespace SKSE {struct SerializationInterface {
 std::vector<char> bytes;size_t position=0;
 bool WriteRecordData(const void* data,uint32_t n){auto* p=static_cast<const char*>(data);bytes.insert(bytes.end(),p,p+n);return true;}
 uint32_t ReadRecordData(void* data,uint32_t n){auto count=std::min<size_t>(n,bytes.size()-position);std::memcpy(data,bytes.data()+position,count);position+=count;return static_cast<uint32_t>(count);}
 bool ResolveFormID(uint32_t old,uint32_t& resolved){resolved=old;return old!=99;}
};}
'''+header+r'''
int main(){
 Papyrus::Tracking data;
 data.Add(data._factions,99,"missing");data.Add(data._factions,2,"valid");data.Add(data._actors,3,"event");
 data.Add(data._actors,3,"event");assert(data.Callbacks(data._actors,3).size()==1);
 SKSE::SerializationInterface io;data.Save(&io);data.Revert(nullptr);data.Load(&io,static_cast<uint32_t>(io.bytes.size()));
 assert(!data.Contains(data._factions,99)&&data.Contains(data._factions,2));
 const auto snapshot=data.Callbacks(data._actors,3);data.Remove(data._actors,3,"event");assert(!data.Contains(data._actors,3)&&snapshot[0]=="event");
 // Every truncation must reject the entire record, without partial registration.
 for(size_t n=0;n<io.bytes.size();++n){auto bad=io;bad.bytes.resize(n);bad.position=0;data.Load(&bad,static_cast<uint32_t>(n));assert(data._actors.empty()&&data._factions.empty());}
 auto invalid=io;invalid.position=0;std::fill(invalid.bytes.begin(),invalid.bytes.begin()+8,'\xff');data.Load(&invalid,static_cast<uint32_t>(invalid.bytes.size()));assert(data._actors.empty());
 auto delimiter=io;delimiter.position=0;delimiter.bytes.back()=0;data.Load(&delimiter,static_cast<uint32_t>(delimiter.bytes.size()));assert(data._actors.empty()&&data._factions.empty());
 std::vector<std::thread> workers;
 for(int i=0;i<4;++i)workers.emplace_back([&]{for(int j=0;j<1000;++j){data.Add(data._actors,3,"event");auto callbacks=data.Callbacks(data._actors,3);data.Remove(data._actors,3,"event");}});
 for(auto& t:workers)t.join();
 std::cout<<"PASS: production tracking v1 roundtrip, unresolved IDs, every truncation, malformed counts/delimiter and concurrent callbacks\n";
}
'''
run('tracking',code)
