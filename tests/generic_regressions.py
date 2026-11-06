"""Generic utility regressions. C++ production bodies use engine stand-ins."""
from pathlib import Path
import os
import runpy
import subprocess
import tempfile
import wave
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def extract(path, signature):
    text = (ROOT / path).read_text(encoding='utf-8')
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


code = r'''
#include <cassert>
#include <string>
#include <vector>
#include <functional>
#include <cstdint>
#include <cstdarg>
namespace RE {
struct ConsoleLog {
 std::vector<std::string> text;
 static ConsoleLog* GetSingleton(){static ConsoleLog c;return &c;}
 void Print(const char* fmt,...) {
  assert(std::string(fmt)=="%s");
  va_list args; va_start(args,fmt);text.emplace_back(va_arg(args,const char*));va_end(args);
 }
};
struct Point {float x=0,y=0,z=0;};
struct TESObjectREFR {Point GetPosition(){return {};}};
struct BSContainer {enum ForEachResult{kContinue,kStop};};
struct Cell {
 struct Coord{float worldX=-2000,worldY=-2000;} coord;
 bool attached=true,coordinates=true;
 bool IsAttached(){return attached;}
 Coord* GetCoordinates(){return coordinates?&coord:nullptr;}
 void ForEachReferenceInRange(Point,float,std::function<BSContainer::ForEachResult(TESObjectREFR*)> cb){TESObjectREFR r;cb(&r);}
};
struct Grid {uint32_t length=5;Cell cells[25];int visits=0;Cell* GetCell(int x,int y){++visits;return &cells[x*5+y];}};
struct TES {Cell* interiorCell=nullptr;Grid* gridCells=nullptr;static TES* GetSingleton(){static TES t;return &t;}};
}
'''
code += extract('src/Util/Misc.h', 'inline void PrintConsole(')
code += extract('src/Util/World.h', 'inline void ForEachObjectInRange(')
code += r'''
int main(){
 auto& messages=RE::ConsoleLog::GetSingleton()->text;
 PrintConsole("");assert(messages.empty());
 PrintConsole("100% ready %s %n");assert(messages.size()==1&&messages[0]=="100% ready %s %n");messages.clear();
 for(int n:{999,1000,1900,4000}) {
  std::string input(n,'A'); PrintConsole(input);std::string result;
  for(auto s:messages){assert(s.size()<1000);if(n>=1000){assert(s.back()=='\n');s.pop_back();}result+=s;}
  assert(result==input);messages.clear();
 }
 RE::Grid grid;RE::TES::GetSingleton()->gridCells=&grid;RE::TESObjectREFR center;int count=0;
 auto visit=[&](auto*){++count;return RE::BSContainer::kContinue;};
 ForEachObjectInRange(&center,100,visit);assert(count==25&&grid.visits==25);
 count=grid.visits=0;ForEachObjectInRange(&center,100,[&](auto*){++count;return RE::BSContainer::kStop;});assert(count==1&&grid.visits==1);
 grid.cells[0].attached=false;grid.cells[1].coordinates=false;grid.cells[2].coord.worldX=5000;
 count=0;ForEachObjectInRange(&center,100,visit);assert(count==22);
 RE::Cell interior;RE::TES::GetSingleton()->interiorCell=&interior;
 count=0;ForEachObjectInRange(&center,100,visit);assert(count==1);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    src, exe = Path(tmp) / 'utility.cpp', Path(tmp) / 'utility'
    src.write_text(code, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)

convert = runpy.run_path(str(ROOT / 'dist/Sound/fx/SexLab/vfx/ConvertMp3ToWav.py'))['convert_mp3_to_wav']


def write_wav(path):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(22050)
        audio.writeframes(b'\0\0' * 8)


for scenario in ('failure', 'missing', 'invalid', 'success', 'existing', 'race'):
    with tempfile.TemporaryDirectory() as tmp:
        source, output = Path(tmp) / 'test.mp3', Path(tmp) / 'test.wav'
        source.write_bytes(b'original')
        if scenario == 'existing':
            output.write_bytes(b'unrelated existing recording')

        def ffmpeg(args, **kwargs):
            assert kwargs.get('check') is True
            if scenario == 'failure':
                raise subprocess.CalledProcessError(1, args)
            if scenario == 'invalid':
                Path(args[-1]).write_bytes(b'not a wave')
            elif scenario in ('success', 'race'):
                write_wav(args[-1])
                if scenario == 'race':
                    output.write_bytes(b'new recording')
            elif scenario == 'existing':
                raise AssertionError('Existing output must not be overwritten')

        with patch('subprocess.run', ffmpeg):
            try:
                convert(tmp)
            except (subprocess.CalledProcessError, RuntimeError, FileExistsError):
                assert scenario in ('failure', 'missing', 'invalid', 'race')
        if scenario == 'success':
            assert not source.exists() and output.exists()
        else:
            assert source.read_bytes() == b'original'
        if scenario in ('existing', 'race'):
            assert output.read_bytes() == (b'unrelated existing recording' if scenario == 'existing' else b'new recording')
print('PASS: console format/chunk integrity, full exterior grid and stop, safe audio success/failure/existing/race cases')

with tempfile.TemporaryDirectory() as tmp:
    source, output = Path(tmp) / 'retry.mp3', Path(tmp) / 'retry.wav'
    source.write_bytes(b'original')
    def successful_ffmpeg(args, **kwargs):
        write_wav(args[-1])
    def failed_copy(src, dst):
        dst.write(b'RIFFpartial')
        raise OSError('simulated disk error')
    with patch('subprocess.run', successful_ffmpeg), patch('shutil.copyfileobj', failed_copy):
        try:
            convert(tmp)
        except OSError:
            pass
        else:
            raise AssertionError('Expected copy failure')
    assert source.read_bytes() == b'original' and not output.exists()
    with patch('subprocess.run', successful_ffmpeg):
        convert(tmp)
    assert not source.exists() and output.exists()
print('PASS: failed output copy retains input, removes own partial file, and permits retry')
