"""Execute production input, speed and close/control functions with engine stand-ins."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
hud = (ROOT / 'src/Thread/Interface/SceneHUD.cpp').read_text()
overlay = (ROOT / 'src/Thread/Interface/Elements/AnimSpeedOverlay.cpp').read_text()
thread_h = (ROOT / 'src/Thread/Thread.h').read_text()
model = (ROOT / 'dist/Source/Scripts/sslThreadModel.psc').read_text()
controller = (ROOT / 'dist/Source/Scripts/sslThreadController.psc').read_text()
initial = re.search(r'float animationPlaybackSpeed\{\s*([0-9.]+)f', thread_h)[1]
assert initial == re.search(r'_AnimationSpeedBase = ([0-9.]+)', model)[1] == '1.25'


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


render = function(overlay, 'void AnimSpeedOverlay::Render(')
assert '_speed' not in overlay
assert render.index('instance->GetAnimationPlaybackSpeed()') > render.index('InvisibleButton("##slpp_inc"')
assert 'SetSpeedControl(a_quest, true)' in function(hud, 'void SceneHUD::Init(')
assert 'SetSpeedControl(a_linkedQst, false)' in function(
    (ROOT / 'src/Thread/Thread.cpp').read_text(), 'void Instance::DestroyInstance(')
assert 'Function SetSpeedHotkeysEnabled(bool abEnabled) native' in model
assert 'SetSpeedHotkeysEnabled(true)' in controller.split('Function EnableHotkeys(')[1].split('EndFunction')[0]
assert 'SetSpeedHotkeysEnabled(false)' in controller.split('Function DisableHotkeys(')[1].split('EndFunction')[0]
assert 'REGISTERFUNC(SetSpeedHotkeysEnabled, "sslThreadModel", false)' in (ROOT / 'src/Papyrus/sslThreadModel.h').read_text()

code = f'constexpr float kInitialSpeed = {initial}f;\n' + r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <functional>
#include <memory>
#include <vector>
namespace RE {
 enum class INPUT_DEVICE {kKeyboard,kMouse,kGamepad};
 enum class BSEventNotifyControl {kContinue};
 template<class T>struct BSTEventSource {};
 struct TESQuest {};
 struct UI {bool paused=false; static UI* GetSingleton(){static UI u;return &u;} bool GameIsPaused(){return paused;}};
 struct BSInputDeviceManager {
  int registrations=0;
  static BSInputDeviceManager* GetSingleton(){static BSInputDeviceManager m;return &m;}
  void AddEventSink(void*){++registrations;}
 };
 struct ButtonEvent;
 struct InputEvent {
  virtual ~InputEvent()=default;
  InputEvent* next=nullptr;INPUT_DEVICE device=INPUT_DEVICE::kKeyboard;
  INPUT_DEVICE GetDevice(){return device;}
  virtual ButtonEvent* AsButtonEvent(){return nullptr;}
 };
 struct ButtonEvent:InputEvent {
  uint32_t key;bool down;
  ButtonEvent(uint32_t k,bool d=true,INPUT_DEVICE dev=INPUT_DEVICE::kKeyboard):key(k),down(d){device=dev;}
  ButtonEvent* AsButtonEvent()override{return this;}
  bool IsDown(){return down;}uint32_t GetIDCode(){return key;}
 };
}
namespace SKSE {
 struct Tasks {
  std::vector<std::function<void()>> pending;
  void AddTask(std::function<void()> f){pending.push_back(f);}
  void Drain(){auto tasks=std::move(pending);pending.clear();for(auto& task:tasks)task();}
 } tasks;
 Tasks* GetTaskInterface(){return &tasks;}
}
struct Instance {
 float animationPlaybackSpeed=kInitialSpeed;
 static Instance* GetInstance(RE::TESQuest*);
 void SetAnimationPlaybackSpeed(float value){animationPlaybackSpeed=value;}
 float GetAnimationPlaybackSpeed() const;
};
Instance instance;RE::TESQuest quest;bool available=true;
Instance* Instance::GetInstance(RE::TESQuest* q){return q==&quest&&available?&instance:nullptr;}
namespace Script {
 using CallbackPtr=int;
 inline float baseSpeed=kInitialSpeed;
 RE::TESQuest* GetScriptObject(RE::TESQuest* q,const char*){return q;}
 void DispatchMethodCall(RE::TESQuest*,const char*,int,float value){baseSpeed=value;}
}
namespace logger {void info(const char*){}}
struct AnimSpeedOverlay {
 static void OnSpeedChange(RE::TESQuest*,float);
 static void StepSpeed(RE::TESQuest*,bool);
};
enum class PanelId {kNone,kOffsetAdjust};
struct SceneHUD {
 struct Elements {AnimSpeedOverlay animSpeedOverlay;};
 std::unique_ptr<Elements> _elements=std::make_unique<Elements>();
 struct Window {void SetBlocksInput(bool){}void Close(){}} _window;
 RE::TESQuest* _linkedThread=&quest;void* _threadScript=nullptr;
 RE::TESQuest* _speedThread=nullptr;
 uint64_t _controlGeneration=0;bool _focused=false,_inputRegistered=false;
 PanelId _activePanel=PanelId::kNone;
 static SceneHUD& GetSingleton(){static SceneHUD singleton;return singleton;}
 bool IsActive()const{return _linkedThread!=nullptr;}
 void SetSpeedControl(RE::TESQuest*,bool);
 bool CanAdjustSpeed()const;
 void Destroy();
 RE::BSEventNotifyControl ProcessEvent(RE::InputEvent* const*,RE::BSTEventSource<RE::InputEvent*>*);
};
'''
code += function(thread_h, 'float GetAnimationPlaybackSpeed()').replace(
    'float GetAnimationPlaybackSpeed()', 'float Instance::GetAnimationPlaybackSpeed()')
for source, signature in [
    (overlay, 'void AnimSpeedOverlay::OnSpeedChange('),
    (overlay, 'void AnimSpeedOverlay::StepSpeed('),
    (hud, 'void SceneHUD::SetSpeedControl('),
    (hud, 'void SceneHUD::Destroy('),
    (hud, 'bool SceneHUD::CanAdjustSpeed('),
    (hud, 'RE::BSEventNotifyControl SceneHUD::ProcessEvent('),
]:
    code += '\n' + function(source, signature)
code += r'''
int main(){
 auto& h=SceneHUD::GetSingleton();
 auto send=[&](RE::InputEvent& e){RE::InputEvent* p=&e;h.ProcessEvent(&p,nullptr);};
 auto drain=[](){SKSE::tasks.Drain();};
 auto speed=[](){return instance.GetAnimationPlaybackSpeed();};
 RE::ButtonEvent right(205),left(203),release(205,false),other(204),mouse(205,true,RE::INPUT_DEVICE::kMouse);
 send(right);assert(SKSE::tasks.pending.empty());
 h.SetSpeedControl(&quest,true);h.SetSpeedControl(&quest,true);
 assert(RE::BSInputDeviceManager::GetSingleton()->registrations==1);
 send(right);assert(speed()==kInitialSpeed&&SKSE::tasks.pending.size()==1);
 drain();assert(speed()==1.5f&&Script::baseSpeed==1.5f);
 send(left);drain();assert(speed()==1.25f);
 send(release);send(other);send(mouse);RE::InputEvent unknown;send(unknown);
 h.ProcessEvent(nullptr,nullptr);assert(SKSE::tasks.pending.empty());
 RE::UI::GetSingleton()->paused=true;send(right);RE::UI::GetSingleton()->paused=false;
 h._focused=true;h._activePanel=PanelId::kOffsetAdjust;send(right);
 assert(SKSE::tasks.pending.empty());
 // Closing the actual HUD destroys its elements, but must not disable arrows.
 instance.SetAnimationPlaybackSpeed(2.0f);
 h.Destroy();assert(!h.IsActive()&&!h._elements&&!h._focused);
 send(right);drain();assert(speed()==2.25f&&Script::baseSpeed==2.25f);
 send(left);drain();assert(speed()==2.0f);
 // New UI elements must not replace the authoritative speed.
 h._linkedThread=&quest;h._elements=std::make_unique<SceneHUD::Elements>();
 h.SetSpeedControl(&quest,true);
 assert(speed()==2.0f);send(right);drain();assert(speed()==2.25f);
 instance.SetAnimationPlaybackSpeed(1.75f);send(left);drain();assert(speed()==1.5f);
 send(right);RE::UI::GetSingleton()->paused=true;drain();assert(speed()==1.5f);RE::UI::GetSingleton()->paused=false;
 // Disable/re-enable the same quest must invalidate already queued presses.
 send(right);h.SetSpeedControl(&quest,false);h.SetSpeedControl(&quest,true);
 drain();assert(speed()==1.5f);
 send(right);available=false;drain();assert(speed()==1.5f);available=true;
 h.SetSpeedControl(&quest,false);send(right);assert(SKSE::tasks.pending.empty());
 h.SetSpeedControl(&quest,true);RE::TESQuest otherQuest;
 h.SetSpeedControl(&otherQuest,false);send(right);drain();assert(speed()==1.75f);
 for(int n=0;n<30;++n){send(right);drain();}assert(speed()==3&&Script::baseSpeed==3);
 for(int n=0;n<30;++n){send(left);drain();}assert(speed()==.25f&&Script::baseSpeed==.25f);
 right.next=&left;send(right);drain();assert(speed()==.25f);
}
'''
with tempfile.TemporaryDirectory(prefix='sexlab-arrow-keys-') as directory:
    source = Path(directory) / 'test.cpp'
    binary = Path(directory) / 'test'
    source.write_text(code)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: production handlers: hidden HUD, recreation, actual-speed increments, bounds, pause/panel guards, control lifecycle and stale tasks; render reads actual speed (source check)')
