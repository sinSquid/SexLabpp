"""Fourth full review: actual queue/record/parser functions and scan bounds."""
import os
from pathlib import Path
import subprocess
import tempfile
from source_regressions import ROOT, function, run

source = (ROOT/'src/Util/AsyncIO.cpp').read_text()
if os.getenv('REVIEW_BASE'):
    source = subprocess.check_output(['git','show',f"{os.environ['REVIEW_BASE']}:src/Util/AsyncIO.cpp"],cwd=ROOT,text=True)
queue = function(source, 'class TaskConsumer final') + ';\n'
code = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <functional>
#include <future>
#include <iostream>
#include <mutex>
#include <thread>
using namespace std::chrono_literals;
namespace logger {template<class... T>void error(T&&...){} }
#ifdef __cpp_lib_move_only_function
using Task=std::move_only_function<void()>;
#else
// Apple libc++ lacks move_only_function; preserve move-only ownership in a
// minimal callable stand-in while exercising the production queue algorithm.
class Task {
 struct Base {virtual ~Base()=default;virtual void call()=0;};
 template<class F>struct Impl:Base {F f;Impl(F x):f(std::move(x)){}void call()override{f();}};
 std::unique_ptr<Base> ptr;
 public:
 template<class F>Task(F f):ptr(std::make_unique<Impl<F>>(std::move(f))){}
 Task(Task&&)=default;Task& operator=(Task&&)=default;
 void operator()(){ptr->call();}
};
#endif
struct LaunchThread {
 static inline bool fail=false;
 static inline std::promise<void>* stopped=nullptr;
 std::jthread worker;
 LaunchThread()=default;
 template<class F>LaunchThread(F f){if(fail){fail=false;throw std::runtime_error("injected launch failure");}worker=std::jthread(std::move(f));}
 LaunchThread(LaunchThread&&)=default;LaunchThread& operator=(LaunchThread&&)=default;
 bool joinable()const{return worker.joinable();}void join(){worker.join();}
 bool request_stop(){auto result=worker.request_stop();if(stopped)stopped->set_value();return result;}
};
'''+queue.replace('std::jthread', 'LaunchThread').replace('std::move_only_function<void()>', 'Task')+r'''
int main(){
 std::atomic_int completed=0;
 // Hold the first task until the destructor has requested shutdown; remaining
 // accepted tasks must still run. A task throwing must not stop the queue.
 std::promise<void> release,started;auto gate=release.get_future().share();
 auto consumer=std::make_unique<TaskConsumer>();
 consumer->Submit([&, token=std::make_unique<int>(1)]{started.set_value();gate.wait();completed+=*token;});
 started.get_future().wait();
 consumer->Submit([]{throw std::runtime_error("task failure");});
 for(int i=0;i<50;++i)consumer->Submit([&]{++completed;});
 std::promise<void> stopped;auto stoppedReady=stopped.get_future();LaunchThread::stopped=&stopped;
 auto shutdown=std::async(std::launch::async,[&]{consumer.reset();});
 assert(stoppedReady.wait_for(2s)==std::future_status::ready);
 assert(shutdown.wait_for(20ms)==std::future_status::timeout);
 release.set_value();assert(shutdown.wait_for(2s)==std::future_status::ready);shutdown.get();
 LaunchThread::stopped=nullptr;assert(completed==51);
 // Failed launch must neither retain an unaccepted task nor poison running state.
 TaskConsumer recovering;LaunchThread::fail=true;bool rejected=false;
 try{recovering.Submit([&]{completed+=1000;});}catch(const std::exception&){rejected=true;}
 assert(rejected);
 std::promise<void> done;auto ready=done.get_future();
 recovering.Submit([&]{++completed;done.set_value();});
 assert(ready.wait_for(2s)==std::future_status::ready);assert(completed==52);
 std::cout<<"PASS: queue shutdown drains accepted tasks, task exceptions are isolated, failed launch is recoverable\n";
}
'''
# Use the standard C++23 callable when available; otherwise a move-only stand-in.
with tempfile.TemporaryDirectory() as temp:
    cpp=Path(temp)/'queue.cpp';cpp.write_text(code);binary=Path(temp)/'queue'
    subprocess.run([os.environ.get('CXX','clang++'),'-std=c++23','-O1','-pthread',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)

code = r'''
#include <algorithm>
#include <cassert>
#include <cstring>
#include <iostream>
#include <string_view>
#include <vector>
#include "Util/RecordIO.h"
struct Stream {
 std::vector<char> bytes;size_t pos=0;int failAfter=-1;
 bool WriteRecordData(const void* data,uint32_t size){if(failAfter==0)return false;if(failAfter>0)--failAfter;assert(data);auto p=static_cast<const char*>(data);bytes.insert(bytes.end(),p,p+size);return true;}
 uint32_t ReadRecordData(void* out,uint32_t size){auto n=std::min<size_t>(size,bytes.size()-pos);std::memcpy(out,bytes.data()+pos,n);pos+=n;return static_cast<uint32_t>(n);}
};
struct EmptyEngineString {size_t length()const{return 0;}const char* data()const{return nullptr;}};
int main(){
 Stream stream;
 char raw[3]={'a','b','c'};Util::WriteRecordString(&stream,std::string_view(raw,3));
 Util::WriteRecordString(&stream,std::string_view{});Util::WriteRecordString(&stream,EmptyEngineString{});
 Util::RecordReader reader(&stream,static_cast<uint32_t>(stream.bytes.size()));
 assert(reader.String()=="abc");assert(reader.String().empty());assert(reader.String().empty());assert(reader.Remaining()==0);
 // Same v1 representation: uint64 byte count includes the trailing NUL.
 assert(stream.bytes.size()==12+9+9);assert(stream.bytes[11]=='\0');
 Stream zero;Util::WriteRecord(&zero,uint64_t{0});Util::RecordReader invalid(&zero,8);bool failed=false;
 try{invalid.Count(0);}catch(const std::exception&){failed=true;}assert(failed);
 for(int fail=0;fail<3;++fail){Stream broken;broken.failAfter=fail;failed=false;try{Util::WriteRecordString(&broken,std::string_view(raw,3));}catch(const std::exception&){failed=true;}assert(failed);}
 std::cout<<"PASS: record string slices/null-data empty strings preserve wire format; zero stride and failed writes reject safely\n";
}
'''
run('full4_records',code)

header=(ROOT/'src/Util/FormLookup.h').read_text().replace('#pragma once','')
code=r'''
#include <cassert>
#include <charconv>
#include <cstdint>
#include <format>
#include <iostream>
#include <string>
#include <string_view>
#include <type_traits>
namespace RE {
using FormID=uint32_t;
struct TESDataHandler{static TESDataHandler* GetSingleton(){static TESDataHandler h;return &h;}uint32_t LookupFormID(uint32_t id,std::string_view file){return file=="test.esp"?id+100:0;}};
struct File{const char* GetFilename(){return "test.esp";}};
struct TESForm{template<class T>static T* LookupByID(uint32_t){return nullptr;}File* GetFile(int){return nullptr;}uint32_t GetFormID(){return 1;}uint32_t GetLocalFormID(){return 1;}};
}
'''+header+r'''
int main(){
 assert(Util::FormFromString(std::string_view{})==0);
 assert(Util::FormFromString("0XFF")==255);assert(Util::FormFromString("0xff")==255);
 assert(Util::FormFromString("0X10|test.esp")==116);
 assert(Util::FormFromString("0x")==0);assert(Util::FormFromString("|test.esp")==0);
 assert(Util::FormFromString("12junk")==0);assert(Util::FormFromString("123 ")==123);
 for(int base:{-1,0,1,37,100})assert(Util::FormFromString("10",base)==0);
 assert(Util::FormFromString("10",2)==2);assert(Util::FormFromString("10",36)==36);
 assert(Util::FormFromString("0x10",10)==0);
 std::cout<<"PASS: form parser checks base/range, empty values, upper/lower hex prefixes and module IDs\n";
}
'''
run('full4_forms',code)

source=(ROOT/'src/Registry/Define/Furniture.cpp').read_text()
code='#include <cstdint>\n#include <cmath>\n#include <limits>\n#include <cassert>\n#include <iostream>\n'+function(source,'uint32_t FurnitureScanSteps(')+r'''
int main(){
 assert(FurnitureScanSteps(32,8)==9);assert(FurnitureScanSteps(0,8)==1);
 assert(FurnitureScanSteps(127.5f,1)==256);assert(FurnitureScanSteps(128,1)==0);
 for(float radius:{-1.f,1e30f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})assert(FurnitureScanSteps(radius,8)==0);
 for(float step:{0.f,-1.f,0.5f,std::numeric_limits<float>::infinity(),std::numeric_limits<float>::quiet_NaN()})assert(FurnitureScanSteps(32,step)==0);
 // Integer counters advance even when float world coordinates cannot add step.
 float world=1e20f;assert(world+8==world);int visits=0;
 for(uint32_t x=0;x<FurnitureScanSteps(32,8);++x)for(uint32_t y=0;y<FurnitureScanSteps(32,8);++y)++visits;
 assert(visits==81);
 std::cout<<"PASS: furniture scan count bounds reject excessive/nonfinite input and counters stay finite at large coordinates\n";
}
'''
run('full4_grid',code)
assert 'ix < scanSteps' in source and 'iy < scanSteps' in source
assert 'attempt < 64' in source and 'std::ranges::find(hitList, res.hitObject)' in source
source=(ROOT/'src/Thread/Interface/UI/Theme.cpp').read_text()
assert 'Util::AtomicWrite(path, buffer)' in source and 'std::ios::trunc' not in source
print('PASS: source contracts for bounded physics retries and atomic theme publication (not engine execution)')
