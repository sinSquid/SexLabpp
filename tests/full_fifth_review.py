"""Voice selection/editing and non-destructive audio rename regressions."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from source_regressions import ROOT, function, run


def source(path):
    if os.getenv('REVIEW_BASE'):
        return subprocess.check_output(['git','show',f"{os.environ['REVIEW_BASE']}:{path}"],cwd=ROOT,text=True)
    return (ROOT/path).read_text()


voice_source=source('src/Registry/Define/Voice.cpp')
code=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <mutex>
#include <shared_mutex>
#include <string>
#include <vector>
namespace RE {struct TESSound{int id;};using BSFixedString=std::string;}
namespace YAML {class Node;}
namespace logger {template<class... T>void error(T&&...){} }
enum class LegacyVoice {Hot,Mild,Medium};
enum class VoiceAnnotation {None=0,Submissive=1,Dominant=2,Muffled=128};
namespace REX {template<class E>struct EnumSet {
 E value;EnumSet(E e):value(e){}uint32_t underlying()const{return static_cast<uint32_t>(value);}
 bool operator==(const EnumSet&)const=default;bool operator!=(E e)const{return value!=e;}
 void operator|=(E e){value=E(underlying()|static_cast<uint32_t>(e));}
};}
'''+function(source('src/Registry/Define/Voice.h'),'struct VoiceSet').replace('      private:', '      public:')+r''';
struct Voice {
 VoiceSet defaultset{false};std::vector<VoiceSet> extrasets;
 const VoiceSet& GetApplicableSet(REX::EnumSet<VoiceAnnotation>)const;
 RE::TESSound* PickSound(LegacyVoice)const;
};
struct Library {
 std::map<std::string,Voice> voices;std::shared_mutex _mVoice;
 void SetVoiceSound(RE::BSFixedString,LegacyVoice,RE::TESSound*);
};
'''
# The bool constructor has a braced member initializer; keep its whole source
# slice instead of treating the initializer's first brace as its function body.
a=voice_source.index('    VoiceSet::VoiceSet(bool');b=voice_source.index('    RE::TESSound* VoiceSet::Get(uint32_t',a)
code+=voice_source[a:b]
for sig in ('const VoiceSet& Voice::GetApplicableSet','RE::TESSound* Voice::PickSound(LegacyVoice',
            'RE::TESSound* VoiceSet::Get(uint32_t','RE::TESSound* VoiceSet::Get(LegacyVoice','void VoiceSet::SetSound('):
    code+=function(voice_source,sig)+'\n'
code+=function(source('src/Registry/Library.cpp'),'void Library::SetVoiceSound(')+r'''
VoiceSet set(RE::TESSound* sound,VoiceAnnotation flags){VoiceSet s(false);s.annotations=flags;s.data={{sound,0},{sound,75}};return s;}
int main(){
 RE::TESSound base{0},sub{1},muffled{2},exact{3},edit{4},hot{5};
 Library lib;auto& v=lib.voices["voice"];v.defaultset=set(&base,VoiceAnnotation::None);
 v.extrasets={set(&base,VoiceAnnotation::None),set(&sub,VoiceAnnotation::Submissive)};
 assert(v.GetApplicableSet(VoiceAnnotation(129)).Get(0)==&sub);
 v.extrasets.push_back(set(&muffled,VoiceAnnotation::Muffled));
 assert(v.GetApplicableSet(VoiceAnnotation(129)).Get(0)==&muffled);
 v.extrasets.push_back(set(&exact,VoiceAnnotation(129)));
 assert(v.GetApplicableSet(VoiceAnnotation(129)).Get(0)==&exact);
 lib.SetVoiceSound("voice",LegacyVoice::Medium,&edit);
 assert(v.PickSound(LegacyVoice::Medium)==&edit);assert(v.defaultset.Get(0)==&base);
 assert(v.extrasets[2].Get(0)==&muffled);
 lib.SetVoiceSound("voice",LegacyVoice::Hot,&hot);
 assert(v.defaultset.Get(LegacyVoice::Hot)==&hot);
 assert(v.GetApplicableSet(VoiceAnnotation::Submissive).Get(LegacyVoice::Hot)==&hot);
 assert(v.extrasets[2].Get(LegacyVoice::Hot)==&muffled);
 v.extrasets.clear();lib.SetVoiceSound("voice",LegacyVoice::Medium,&edit);
 assert(v.PickSound(LegacyVoice::Medium)==&edit);
 assert(v.extrasets[0].Get(LegacyVoice::Hot)==&hot);
 // Preserve threshold semantics, including repeated thresholds and below-minimum.
 auto thresholds=set(&base,VoiceAnnotation::None);thresholds.data.clear();
 for(int n=0;n<200;++n)thresholds.data.emplace_back(n%2?&base:&sub,static_cast<uint8_t>(n/2+5));
 for(uint32_t priority=0;priority<300;++priority){RE::TESSound* expected=nullptr;for(auto& [sound,level]:thresholds.data)if(level<=priority)expected=sound;assert(thresholds.Get(priority)==expected);}
 thresholds.data.clear();assert(thresholds.Get(0)==nullptr);
 std::cout<<"PASS: complete voice condition fallback, matching legacy edits, missing-set creation and threshold parity\n";
}
'''
run('full5_voice',code)

# YAML/engine integration remains separate; these are explicit source contracts.
constructor=voice_source[:voice_source.index('const VoiceSet& Voice::GetApplicableSet')]
tags=constructor[constructor.index('tags([&]'):constructor.index('defaultset(a_node)')]
assert 'if (!node.IsDefined())' in tags
save=function(voice_source,'void Voice::SaveToFile(')
for field in ('root["DisplayName"]','root["Actor"]["Pitch"]','root["Tags"] = YAML::Node(YAML::NodeType::Sequence)'):
    assert field in save
assert 'Util::AtomicWrite(path, YAML::Dump(root))' in save
assert 'Unable to save voice' in function(source('src/Registry/Library.cpp'),'void Library::WriteVoiceToFile(')
print('PASS: voice metadata/empty-tags/atomic-publication source contracts (not yaml-cpp/game execution)')

spec=importlib.util.spec_from_file_location('voice_rename',ROOT/'dist/Sound/fx/SexLab/vfx/VoiceRename.py')
rename=importlib.util.module_from_spec(spec);spec.loader.exec_module(rename)
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);folder=root/'P'/'soft';folder.mkdir(parents=True)
    (folder/'a.wav').write_bytes(b'A');(folder/'P_s01.wav').write_bytes(b'B')
    rename.rename_files_in_directory(root)
    assert (folder/'P_s01.wav').read_bytes()==b'A' and (folder/'P_s02.wav').read_bytes()==b'B'
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    rename.rename_files_in_directory(root)
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==before
    for index in range(3,121):
        (folder/f'P_s{index:02d}.wav').write_bytes(str(index).encode())
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    rename.rename_files_in_directory(root)
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==before

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);folder=root/'P'/'soft';folder.mkdir(parents=True)
    (folder/'a.wav').write_bytes(b'A');(folder/'b.wav').write_bytes(b'B')
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    real_link=rename.os.link;calls=0
    def fail_second(*args,**kwargs):
        global calls
        calls+=1
        if calls==2:
            raise OSError('injected publish failure')
        return real_link(*args,**kwargs)
    with patch.object(rename.os,'link',fail_second):
        try:
            rename.rename_files_in_directory(root)
        except OSError:
            pass
        else:
            raise AssertionError('publication failure ignored')
    assert {p.name:p.read_bytes() for p in folder.iterdir()}==before
    # Occupied target that is not an audio input must be rejected before staging.
    (folder/'P_s01.wav').mkdir()
    try:
        rename.rename_files_in_directory(root)
    except FileExistsError:
        pass
    else:
        raise AssertionError('occupied target not rejected')
    assert (folder/'a.wav').read_bytes()==b'A'
    assert not list(folder.glob('.voice-rename-*'))

with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);folder=root/'P'/'soft';folder.mkdir(parents=True)
    (folder/'a.wav').write_bytes(b'A')
    with patch.object(rename.os,'link',side_effect=OSError('persistent publish/restore failure')):
        try:
            rename.rename_files_in_directory(root)
        except RuntimeError as error:
            assert 'preserved recovery files' in str(error)
        else:
            raise AssertionError('failed rollback was hidden')
    staging=next(folder.glob('.voice-rename-*'))
    assert (staging/'0').read_bytes()==b'A'
    assert 'a.wav' in (staging/'manifest.json').read_text()
print('PASS: audio rename collision safety, natural-order idempotence, rollback and retained recovery bytes/manifest')
