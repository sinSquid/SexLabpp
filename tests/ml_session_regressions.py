"""Verify production ML state handoff without a game runtime."""
from source_regressions import ROOT, function, run
source=(ROOT/'src/Thread/NiNode/NiUpdate.cpp').read_text()
code=r'''
#include <cassert>
#include <filesystem>
#include <mutex>
#include <string>
#include <vector>
#include <iostream>
namespace fs=std::filesystem;
constexpr const char* MODELDATAPATH="ModelData";
namespace logger {template<class... T> void info(T&&...) {}}
struct NiType {
 enum class Type {None, A, B, C};
 enum class Cluster {None, AB, C};
 static Cluster GetClusterForType(Type t){return t==Type::None?Cluster::None:t==Type::C?Cluster::C:Cluster::AB;}
};
namespace magic_enum {inline std::string enum_name(NiType::Type){return "type";} inline std::string enum_name(NiType::Cluster c){return c==NiType::Cluster::AB?"AB":"C";}}
struct NiUpdate {
 struct State {NiType::Type type=NiType::Type::None; std::vector<std::string> recordedData; bool enabled=false;size_t frameCount=0;size_t frameInterval=20;};
 struct MLTrainingStatus {NiType::Type type;bool enabled;size_t frameInterval;size_t frameCount;size_t recordedRows;};
 static MLTrainingStatus GetMLTrainingState();
 static std::mutex _mlMutex;
 static State mlTrainingState;
 static void UpdateMLTrainingState(NiType::Type,bool);
};
std::mutex NiUpdate::_mlMutex;
NiUpdate::State NiUpdate::mlTrainingState;
namespace Util {
struct SaveQueue {
 struct Batch {fs::path directory;std::vector<std::string> rows;};
 std::vector<Batch> batches;
 int retries=0;
 static SaveQueue& Get(){static SaveQueue q;return q;}
 void SubmitArchive(fs::path path,std::vector<std::string> rows){
  // A second thread can obtain the frame mutex during queue submission.
  bool available=false;std::thread t([&]{available=NiUpdate::_mlMutex.try_lock();if(available)NiUpdate::_mlMutex.unlock();});t.join();assert(available);
  batches.push_back({std::move(path),std::move(rows)});
 }
 void RetryArchives(){++retries;}
};
}
'''
code='#include <thread>\n'+code+function(source,'void NiUpdate::UpdateMLTrainingState')+function(source,'NiUpdate::MLTrainingStatus NiUpdate::GetMLTrainingState')+r'''
int main(){
 using T=NiType::Type;
 NiUpdate::UpdateMLTrainingState(T::A,true);
 NiUpdate::mlTrainingState.recordedData={"header","old"};
 NiUpdate::UpdateMLTrainingState(T::B,false);
 const auto status=NiUpdate::GetMLTrainingState();
 static_assert(std::is_trivially_copyable_v<decltype(status)>);
 assert(status.type==T::B && !status.enabled && status.recordedRows==2 && status.frameInterval==20);
 assert(NiUpdate::mlTrainingState.recordedData.size()==2);
 assert(Util::SaveQueue::Get().batches.empty());
 NiUpdate::UpdateMLTrainingState(T::C,true);
 assert(NiUpdate::mlTrainingState.recordedData.empty());
 assert(Util::SaveQueue::Get().batches[0].directory==fs::path(MODELDATAPATH)/"AB");
 assert(Util::SaveQueue::Get().batches[0].rows[1]=="old");
 NiUpdate::mlTrainingState.recordedData={"header","new"};
 NiUpdate::UpdateMLTrainingState(T::None,false);
 assert(Util::SaveQueue::Get().batches[1].directory==fs::path(MODELDATAPATH)/"C");
 assert(Util::SaveQueue::Get().batches[1].rows[1]=="new");
 std::cout<<"PASS: production ML cluster handoff and queue submission outside frame mutex\n";
}
'''
run('ml_session',code)
