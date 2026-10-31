"""Compile production menu/alpha methods against deterministic owner and VM stand-ins.

This checks cleanup ownership and stale submissions; it does not render ImGui or
exercise Skyrim/SKSE ABI. Run with CXX set, or g++ on PATH (WSL is supported).
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(path, signature):
    text = (ROOT / path).read_text(encoding='utf-8')
    start = text.index(signature)
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


base = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>
namespace RE {
struct TESQuest { std::int32_t revision{}; };
using BSFixedString = std::string;
struct Actor { float alpha{.4f}; float GetAlpha(){return alpha;} void SetAlpha(float value){alpha=value;} };
}
namespace Registry { struct Stage { const char* id{"stage"}; }; struct Scene { const char* id{"scene"}; }; }
namespace logger { template<class... T> void error(T&&...) {} }
namespace Script {
struct CallbackPtr {};
int calls{}; std::string method;
RE::TESQuest* GetScriptObject(RE::TESQuest* quest,const char*) { return quest; }
template<class T> T GetProperty(RE::TESQuest* quest,const char*) { return T(quest->revision); }
template<class... T> void DispatchMethodCall(RE::TESQuest*, const char* name, CallbackPtr, T&&...) {++calls;method=name;}
}
namespace Thread {
struct Instance {
  struct Data { RE::Actor* actor; RE::Actor* GetActor(){return actor;} };
  struct Position { Data data; std::optional<float> ghostAlpha; };
  std::vector<Position> positions;
  RE::TESQuest* quest{}; Registry::Scene scene; Registry::Stage stage; int selected{-1};
  static inline std::map<RE::TESQuest*,Instance*> live, pending;
  static Instance* GetInstance(RE::TESQuest* q){auto it=live.find(q);return it==live.end()?nullptr:it->second;}
  static Instance* GetPendingInstance(RE::TESQuest* q){auto it=pending.find(q);return it==pending.end()?nullptr:it->second;}
  template<class T> T GetThreadProperty(const char*){return T(quest->revision);}
  Registry::Scene* GetActiveScene(){return &scene;} Registry::Stage* GetActiveStage(){return &stage;}
  Position* GetPosition(RE::Actor* actor){for(auto& p:positions)if(p.data.actor==actor)return &p;return nullptr;}
  void SetCenterRefSelected(std::size_t i){selected=int(i);}
  void RestoreActorAlphas();
};
namespace Interface {
struct SceneHUD { Instance* instance{}; Instance* GetThreadInstance(){return instance;} };
struct ThreadConfigPanel { void OnSetActorAlpha(SceneHUD&,RE::Actor*,int); };
struct FurnSelectMenu {
 struct Item {};
 RE::TESQuest* _linkedThread{}; std::int32_t _ownerRevision{};std::vector<Item> _items;bool visible{};
 void Hide(){visible=false;}void Show(){visible=true;}
 void Open(RE::TESQuest*,const std::vector<Item>&);void HandleSelection(std::size_t);void CancelForThread(RE::TESQuest*);
};
struct StageSelectMenu {
 RE::TESQuest* _linkedThread{};bool _choicePending{},_graphOpen{},visible{},blocks{};
 std::vector<int> _choices;std::vector<float> _choiceScrollOffsets;
 const Registry::Stage* _choiceOrigin{};std::int32_t _choiceRevision{};
 const Registry::Scene* _graphScene{};std::vector<int> _graphNodes,_graphEdges;
 void SetBlocksInput(bool value){blocks=value;}void Hide(){visible=false;}bool IsVisible(){return visible;}
 void RenderSceneGraphView(){}void RenderStageChoiceCard(){}
 void Close();void CancelForThread(RE::TESQuest*);void HideIfIdle();void ClosePendingChoice();
 void OnNextBranchSelected(int);void Render();
};
}}
'''

methods = []
for name in ('Open', 'HandleSelection', 'CancelForThread'):
    methods.append(function('src/Thread/Interface/FurnSelectMenu.cpp', f'void FurnSelectMenu::{name}('))
for name in ('Close', 'CancelForThread', 'HideIfIdle', 'ClosePendingChoice', 'OnNextBranchSelected', 'Render'):
    methods.append(function('src/Thread/Interface/StageSelectMenu.cpp', f'void StageSelectMenu::{name}('))
methods.append(function('src/Thread/Interface/Elements/ThreadConfigPanel.cpp', 'void ThreadConfigPanel::OnSetActorAlpha('))
restore = function('src/Thread/Thread.cpp', 'void Instance::RestoreActorAlphas(')

main = r'''
int main() {
 using namespace Thread;using namespace Thread::Interface;
 RE::TESQuest first{1},other{2};Instance inst;inst.quest=&first;
 FurnSelectMenu furniture;furniture.Open(&first,{{},{}});
 furniture.CancelForThread(&other);assert(furniture.visible && furniture._items.size()==2);
 furniture.CancelForThread(&first);assert(!furniture.visible && !furniture._linkedThread && furniture._items.empty());
 Instance::pending[&first]=&inst;
 furniture.Open(&first,{{},{}});++first.revision;furniture.HandleSelection(1);assert(inst.selected==-1);
 furniture.Open(&first,{{},{}});furniture.HandleSelection(1);assert(inst.selected==1 && !furniture.visible);
 StageSelectMenu choice;
 const auto open=[&] {choice._linkedThread=&first;choice._choicePending=true;choice.visible=true;choice.blocks=true;
   choice._choiceOrigin=&inst.stage;choice._choiceRevision=first.revision;choice._choices={0,1};};
 Instance::live[&first]=&inst;open();choice.CancelForThread(&other);assert(choice.visible);
 choice.CancelForThread(&first);assert(!choice.visible && !choice.blocks && !choice._linkedThread);
 open();++first.revision;choice.OnNextBranchSelected(0);assert(Script::calls==0 && !choice._choicePending);
 open();Instance::live.erase(&first);choice.Render();assert(!choice.visible && !choice.blocks);
 Instance::live[&first]=&inst;open();choice.OnNextBranchSelected(1);
 assert(Script::calls==1 && Script::method=="BranchToCurrent" && !choice._choicePending);
 RE::Actor actor;inst.positions.push_back({{&actor},std::nullopt});SceneHUD hud{&inst};ThreadConfigPanel panel;
 panel.OnSetActorAlpha(hud,&actor,20);panel.OnSetActorAlpha(hud,&actor,0);
 assert(actor.alpha==0 && inst.positions[0].ghostAlpha==.4f);
 inst.RestoreActorAlphas();assert(actor.alpha==.4f && !inst.positions[0].ghostAlpha);
 inst.RestoreActorAlphas();assert(actor.alpha==.4f);
}
'''
source = base + '\nnamespace Thread {\n' + restore + '\n}\nnamespace Thread::Interface {\n' + '\n'.join(methods) + '\n}\n' + main
with tempfile.TemporaryDirectory(prefix='slpp-ui-owner-') as folder:
    directory = Path(folder)
    cpp, binary = directory / 'probe.cpp', directory / ('probe.exe' if os.name == 'nt' else 'probe')
    cpp.write_text(source, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print('PASS: production furniture/branch ownership and alpha snapshot restoration')
