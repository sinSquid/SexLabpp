"""Real revert/alpha cleanup with engine stand-ins; REVIEW_BASE=HEAD checks the baseline."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def source(path):
    if os.environ.get('REVIEW_BASE'):
        return subprocess.check_output(['git','show',os.environ['REVIEW_BASE']+':'+path],cwd=ROOT,text=True)
    return (ROOT/path).read_text(encoding='utf-8')

def function(text,signature):
    start=text.index(signature);brace=text.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

thread=source('src/Thread/Thread.cpp')
animation=source('src/Thread/ThreadAnimation.cpp')
serialization=source('src/Serialization.h')
code=r'''
#include <cassert>
#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <vector>
namespace RE {struct TESQuest{};struct Actor {float alpha=.65f;int writes=0;void SetAlpha(float a){alpha=a;++writes;}};}
namespace SKSE {struct SerializationInterface{};}
namespace Hooks {bool blocked=true;void SetWeaponDrawBlocked(bool b){blocked=b;}}
namespace Interface {
struct Menu {int calls=0;void CancelForThread(RE::TESQuest*){++calls;}};
struct FurnSelectMenu:Menu {static FurnSelectMenu& GetSingleton(){static FurnSelectMenu m;return m;}};
struct StageSelectMenu:Menu {static StageSelectMenu& GetSingleton(){static StageSelectMenu m;return m;}};
struct SceneHUD {int closed=0,disabled=0;static SceneHUD& GetSingleton(){static SceneHUD h;return h;}void Destroy(){++closed;}void SetSpeedControl(RE::TESQuest*,bool){++disabled;}};
}
namespace Interaction::NiSurface {struct Manager {static inline int cleared=0;static void Clear(){++cleared;}};}
std::mutex actorPreparationLock;
std::map<unsigned,RE::Actor*> actorPreparations;
struct Instance {
 RE::TESQuest* linkedQst;
 struct Data {RE::Actor* actor;RE::Actor* GetActor(){return actor;}};
 struct Position {Data data;std::optional<float> ghostAlpha;};
 std::vector<Position> positions;
 static inline std::recursive_mutex _mInstances;
 static inline std::map<RE::TESQuest*,std::uint64_t> creationGenerations;
 static inline std::vector<std::unique_ptr<Instance>> instances,pendingInstances;
 static void CancelPendingCreations();static void RevertInstances();static void DiscardPreparedActors();
 void RestoreActorAlphas();
};
namespace Thread {using Instance=::Instance;namespace Collision {struct CollisionHandler {static void Clear(){}};}}
struct Revertable {void Revert(SKSE::SerializationInterface*){}};
namespace Registry::Statistics {struct StatisticsData:Revertable {static StatisticsData* GetSingleton(){static StatisticsData d;return &d;}};}
namespace Papyrus {struct Tracking:Revertable {static Tracking* GetSingleton(){static Tracking t;return &t;}};}
'''
code+=function(thread,'void Instance::CancelPendingCreations(')
has_cleanup='void Instance::RevertInstances(' in thread
if has_cleanup:
    code+=function(thread,'void Instance::RevertInstances(')
    code+=function(thread,'void Instance::RestoreActorAlphas(')
    code+=function(animation,'void Instance::DiscardPreparedActors(')
code+='struct Serialize {'+function(serialization,'static void RevertCallback(')+'};\n'
code+=r'''
int main(){
 RE::TESQuest a,b;RE::Actor actor;
 auto active=std::make_unique<Instance>();active->linkedQst=&a;active->positions={{{&actor},.65f}};
 Instance::instances.push_back(std::move(active));
 auto pending=std::make_unique<Instance>();pending->linkedQst=&b;Instance::pendingInstances.push_back(std::move(pending));
 Instance::creationGenerations={{&a,1},{&b,2}};actorPreparations[7]=&actor;
 Serialize::RevertCallback(nullptr);
 assert(Instance::instances.empty()&&Instance::pendingInstances.empty());
 assert(Instance::creationGenerations[&a]>1&&Instance::creationGenerations[&b]>2);
 assert(actorPreparations.empty()&&Interaction::NiSurface::Manager::cleared==1);
 assert(actor.writes==0); // Revert must not restore alpha/physics into the old world.
 assert(!Hooks::blocked&&Interface::SceneHUD::GetSingleton().closed==1);
'''
if has_cleanup:
    code+=r'''
 Instance normal;actor.alpha=.2f;normal.positions={{{&actor},.65f},{{nullptr},.4f}};
 normal.RestoreActorAlphas();assert(actor.alpha==.65f&&actor.writes==1);
 assert(!normal.positions[0].ghostAlpha&&!normal.positions[1].ghostAlpha);
 normal.RestoreActorAlphas();assert(actor.writes==1);
'''
code+='}\n'
with tempfile.TemporaryDirectory(prefix='slpp-cleanup-') as tmp:
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    cpp,binary=Path(tmp)/'test.cpp',Path(tmp)/'test'
    cpp.write_text(code,encoding='utf-8')
    subprocess.run([os.getenv('CXX','g++'),'-std=c++23','-pthread',str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True,timeout=10)
print('PASS: old-world state discarded on Revert; normal alpha restoration is exact and idempotent')
