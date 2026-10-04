"""Resource initialization and ML pipeline regressions for the third full review."""
import configparser
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import pandas as pd
from source_regressions import ROOT, function, run

source = (ROOT / 'src/Registry/Library_SaveLoad.cpp').read_text()
if os.getenv('REVIEW_BASE'):
    source = subprocess.check_output(['git', 'show', f"{os.environ['REVIEW_BASE']}:src/Registry/Library_SaveLoad.cpp"], cwd=ROOT, text=True)

support = r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <mutex>
#include <numeric>
#include <string>
#include <thread>
#include <vector>
namespace fs=std::filesystem;
namespace logger {
 inline int errors=0;
 template<class... T>void error(T&&...){++errors;}
 template<class... T>void warn(T&&...){}
 template<class... T>void info(T&&...){}
}
'''
code = support + r'''
struct Library {uint8_t InitializeCumFxType(const fs::directory_entry&)const noexcept;};
''' + function(source, 'uint8_t Library::InitializeCumFxType(') + r'''
int main(){
 const auto path=fs::temp_directory_path()/std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
 fs::create_directories(path);Library lib;
 for(auto name:{"1extra.dds","01.dds","+1.dds","0.dds","256.dds","-1.dds"}){
  {std::ofstream file(path/name);file<<"data";}
  assert(lib.InitializeCumFxType(fs::directory_entry(path))==0);
  fs::remove(path/name);
 }
 for(int i=1;i<=255;++i){std::ofstream file(path/(std::to_string(i)+".dds"));file<<"data";}
 assert(lib.InitializeCumFxType(fs::directory_entry(path))==255);
 fs::remove(path/"100.dds");assert(lib.InitializeCumFxType(fs::directory_entry(path))==0);
 auto entry=fs::directory_entry(path);fs::remove_all(path);
 // Directory existed during discovery but disappeared before iteration.
 assert(lib.InitializeCumFxType(entry)==0);
 std::cout<<"PASS: FX canonical names, 255 entries, missing index and vanished directory\n";
}
'''
run('full3_fx', code)

# Use the actual initializer, with engine methods as counters. A launch fixture
# injects construction failure at each position and runs real threads otherwise.
code = support + r'''
struct TestThread {
 static inline int attempts=0,failAt=-1;
 std::jthread worker;
 template<class F>TestThread(F task){if(attempts++==failAt)throw std::runtime_error("injected thread creation failure");worker=std::jthread(std::move(task));}
 TestThread(TestThread&&)=default;
 void join(){worker.join();}
};
struct Library {
 std::array<std::atomic_int,5> calls{};
 std::vector<int> packages,scenes,voices,savedPitches,savedVoices,expressions,furnitures;
 std::vector<std::vector<int>> fxList;
 int GetSceneCount(){return 0;}
 void InitializeScenes()noexcept{++calls[0];}void InitializeVoice()noexcept{++calls[1];}
 void InitializeExpressions()noexcept{++calls[2];}void InitializeFurnitures()noexcept{++calls[3];}
 void InitializeCumFx()noexcept{++calls[4];}void Initialize()noexcept;
};
'''
code += function(source, 'void Library::Initialize()').replace('std::jthread', 'TestThread')
code += r'''
int main(){for(int fail=-1;fail<5;++fail){TestThread::attempts=0;TestThread::failAt=fail;Library lib;lib.Initialize();for(auto& n:lib.calls)assert(n==1);}std::cout<<"PASS: all five initializers run exactly once, including thread launch failure and VR mode\n";}
'''
run('full3_initialization', code)
run('full3_initialization_vr', '#define SKYRIMVR\n'+code)

code = support + r'''
namespace RE {using BSFixedString=std::string;}
namespace YAML {
 struct Node {
  static inline int lookups=0;
  std::string text;bool defined=true;
  std::vector<std::pair<Node,Node>> entries;
  template<class T>T as()const{return text;}
  bool IsDefined()const{return defined;}
  Node operator[](const std::string& id)const{++lookups;for(auto& p:entries)if(p.first.text==id)return p.second;return {"",false,{}};}
  auto begin()const{return entries.begin();}auto end()const{return entries.end();}
 };
 Node LoadFile(const std::string&){Node root;root.entries.push_back({{"scene42"},{"updated"}});root.entries.push_back({{"unknown"},{"ignore"}});return root;}
}
struct Scene {std::string id;int loads=0;void Load(const YAML::Node&){++loads;}};
struct Library {
 static inline const char* SCENE_USER_CONFIG;
 std::map<std::string,Scene*> sceneMap;
 std::mutex _mScenes;
 bool FolderExists(const char*,bool){return true;} // Simulate removal after preflight.
 void InitializeSceneSettings()noexcept;
};
'''+function(source, 'void Library::InitializeSceneSettings(')+r'''
int main(){
 const auto path=fs::temp_directory_path()/std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
 fs::create_directories(path);{std::ofstream file(path/"package.yaml");file<<"placeholder";}
 auto pathString=path.string();Library::SCENE_USER_CONFIG=pathString.c_str();Library lib;
 std::vector<Scene> scenes(10000);
 for(int i=0;i<10000;++i){scenes[i].id="scene"+std::to_string(i);lib.sceneMap.emplace(scenes[i].id,&scenes[i]);}
 lib.InitializeSceneSettings();assert(scenes[42].loads==1);assert(scenes[41].loads==0);
 assert(YAML::Node::lookups==0); // No full registry scan for a two-key package.
 fs::remove_all(path);auto errors=logger::errors;lib.InitializeSceneSettings();assert(logger::errors==errors+1);
 std::cout<<"PASS: scene settings visit present keys, ignore unknown IDs, and survive directory disappearance\n";
}
'''
run('full3_scene_settings', code)

# All filesystem-enumerating initializers must catch enumeration exceptions at
# function scope; this source check supplements the two behavioral examples.
for name in ('InitializeSceneSettings', 'InitializeFurnitures', 'InitializeExpressionsImpl',
             'InitializeExpressionsLegacy', 'InitializeVoiceImpl', 'InitializeVoicePitches',
             'InitializeCumFx', 'InitializeCumFxType'):
    body = function(source, f'Library::{name}(')
    assert body.index('try {') < body.index('directory_iterator')
    assert 'Resource loading failed' in body
print('PASS: exception-boundary source contracts for all eight resource enumerators')

sys.path.insert(0, str(ROOT / 'scripts/ML'))
import main as training
import export as exporter

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    small = pd.DataFrame({'Label':['Act','Act','None','None'], 'Act_Distance':[0.,1.,3.,4.]})
    assert 'Act' in training.train_binary_model(small, 'Small', root)
    rare = small.iloc[:3]
    assert training.train_binary_model(rare, 'Rare', root) == {}
    multi = pd.DataFrame({'Label':['A','A','B','B','C','C'], 'A_Distance':[0.,1.,3.,4.,6.,7.], 'B_Distance':[7.,6.,4.,3.,1.,0.]})
    assert training.train_softmax_model(multi, 'Multi', root) is not None
    assert training.train_softmax_model(multi.iloc[:-1], 'RareMulti', root) is None

    stale = root / 'models/stale.ini'
    stale.parent.mkdir()
    stale.write_text('[Stale]\nbias=999\n')
    with patch.object(training, 'load_data', return_value={'Small': small.copy()}):
        first = training._run_training(out_dir=root)
        second = training._run_training(out_dir=root)
    assert first != second and first.parent == root / 'models'
    output = root / 'combined.ini'
    exporter.unify_ini_files(second, output)
    parsed = configparser.ConfigParser();parsed.read(output)
    assert parsed.has_section('Act') and not parsed.has_section('Stale')
    assert stale.exists() # Prior artifacts are retained but not republished.

    original = output.read_bytes()
    with patch.object(exporter.os, 'replace', side_effect=OSError('injected replacement failure')):
        try:
            exporter.unify_ini_files(second, output)
        except OSError:
            pass
        else:
            raise AssertionError('replacement failure was ignored')
    assert output.read_bytes() == original
    assert not list(root.glob('.combined.ini.*.tmp'))
    empty = root / 'empty';empty.mkdir()
    exporter.unify_ini_files(empty, output)
    assert output.read_bytes() == original
    exporter.unify_ini_files(empty, root/'not-created.ini')
    assert not (root/'not-created.ini').exists()
print('PASS: small/rare class handling, isolated training runs, stale export exclusion and atomic INI failure recovery')
