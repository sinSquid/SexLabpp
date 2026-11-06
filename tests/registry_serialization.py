"""Exercise production statistics save/load using an in-memory SKSE record.

Version-1 ABI is the measured MSVC x64 layout (16-byte variant, float at0);
this fixture is not evidence about other historical toolchain layouts.
REGISTRY_TEST_BASELINE=HEAD checks that the old writer fails the v2 size contract.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('REGISTRY_TEST_BASELINE')


def read(path, base=None):
    if base:
        return subprocess.check_output(['git', 'show', f'{base}:{path}'], cwd=ROOT).decode('utf-8')
    return (ROOT / path).read_text(encoding='utf-8')


def extract(source, signature):
    start = source.index(signature)
    end = start + re.search(r'\n[ \t]*\{', source[start:]).end()
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


source = read('src/Registry/Stats.cpp', BASE)
# Pin the v1 producer: HEAD becomes the v2 writer after this fix is committed.
original = read('src/Registry/Stats.cpp', '10d56c9ab15f561526a8a2855b2b5776859beb8f')
header = read('src/Registry/Stats.h')
code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <map>
#include <mutex>
#include <set>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
using namespace std;
namespace logger {template<class...T>void info(T...){}template<class...T>void warn(T...){}template<class...T>void error(T...){} }
namespace RE {using FormID=uint32_t; struct BSFixedString {
 const string* p; static const string*intern(string v){static set<string> pool;return &*pool.insert(std::move(v)).first;}
 BSFixedString():p(intern("")){} BSFixedString(const char*s):p(intern(s)){} BSFixedString(string s):p(intern(std::move(s))){}
 const char*data()const{return p->c_str();}size_t length()const{return p->size();}
 friend bool operator<(const BSFixedString&a,const BSFixedString&b){return *a.p<*b.p;}
}; }
static_assert(sizeof(RE::BSFixedString)==8);
static_assert(sizeof(variant<float,RE::BSFixedString>)==16);
namespace SKSE {struct SerializationInterface {
 vector<byte> bytes;size_t offset=0;
 template<class T>bool WriteRecordData(const T&v){return WriteRecordData(&v,sizeof v);}
 bool WriteRecordData(const void*p,uint32_t n){auto b=static_cast<const byte*>(p);bytes.insert(bytes.end(),b,b+n);return true;}
 template<class T>uint32_t ReadRecordData(T&v){return ReadRecordData(&v,sizeof v);}
 uint32_t ReadRecordData(void*p,uint32_t n){if(n>bytes.size()-offset)return 0;memcpy(p,bytes.data()+offset,n);offset+=n;return n;}
 bool ResolveFormID(uint32_t old,uint32_t&out){if(old==99)return false;out=old+1000;return true;}
}; }
namespace stl {template<class S>bool write_string(SKSE::SerializationInterface*i,const S&s){size_t n=s.length()+1;return i->WriteRecordData(n)&&i->WriteRecordData(s.data(),static_cast<uint32_t>(n));}}
struct ActorStats {
'''
code += extract(header, 'enum StatisticID') + ';\n'
code += r'''
 vector<float>_stats=vector<float>(Total);map<RE::BSFixedString,variant<float,RE::BSFixedString>>_custom;
 ActorStats()=default;
 ActorStats(SKSE::SerializationInterface*,uint32_t,uint32_t&);
 void Save(SKSE::SerializationInterface*);
 void SaveLegacy(SKSE::SerializationInterface*);
};
struct StatisticsData {shared_mutex _m;map<RE::FormID,ActorStats>_data;vector<int>_encounters;
 void Load(SKSE::SerializationInterface*,uint32_t,uint32_t);
 void Revert(SKSE::SerializationInterface*);
};
'''
code += extract(source, 'void ActorStats::Save(')
if not BASE:
    helpers = source[source.index('    namespace\n'):source.index('    ActorStats::ActorStats(RE::Actor*')]
    code += helpers
    code += extract(source, 'ActorStats::ActorStats(SKSE::SerializationInterface*')
    code += extract(source, 'void StatisticsData::Load(')
    code += extract(source, 'void StatisticsData::Revert(')
    code += extract(original, 'void ActorStats::Save(').replace('ActorStats::Save(', 'ActorStats::SaveLegacy(', 1)

code += r'''
int main(){
 ActorStats a;a._stats[0]=42.5f;a._custom["number"]=123.25f;a._custom["text"]=RE::BSFixedString{"abc"};
 SKSE::SerializationInterface v2;a.Save(&v2);
 // fixed stats + custom count + two (length+key+tag+payload) entries
 size_t expected=ActorStats::Total*4+8+(8+7+4+4)+(8+5+4+8+4);
 assert(v2.bytes.size()==expected);
'''
if not BASE:
    code += r'''
 uint32_t remaining=static_cast<uint32_t>(v2.bytes.size());ActorStats roundtrip{&v2,2,remaining};
 assert(remaining==0&&v2.offset==v2.bytes.size());
 assert(roundtrip._stats[0]==42.5f&&get<float>(roundtrip._custom.at("number"))==123.25f);
 assert(string(get<RE::BSFixedString>(roundtrip._custom.at("text")).data())=="abc");
 SKSE::SerializationInterface v1;a.SaveLegacy(&v1);assert(v1.bytes.size()==expected+12);
 remaining=static_cast<uint32_t>(v1.bytes.size());ActorStats migrated{&v1,1,remaining};
 assert(remaining==0&&v1.offset==v1.bytes.size());
 assert(migrated._stats[0]==42.5f&&get<float>(migrated._custom.at("number"))==123.25f);
 assert(string(get<RE::BSFixedString>(migrated._custom.at("text")).data())=="abc");
 for(uint32_t version:{1u,2u}){
  SKSE::SerializationInterface stream;stream.WriteRecordData(size_t{2});
  stream.WriteRecordData(uint32_t{99});if(version==1)a.SaveLegacy(&stream);else a.Save(&stream);
  stream.WriteRecordData(uint32_t{77});if(version==1)a.SaveLegacy(&stream);else a.Save(&stream);
  StatisticsData data;data._encounters={1,2};data.Load(&stream,version,static_cast<uint32_t>(stream.bytes.size()));
  assert(data._data.size()==1&&data._data.contains(1077));assert(data._encounters.empty());
  assert(get<float>(data._data.at(1077)._custom.at("number"))==123.25f);
  assert(stream.offset==stream.bytes.size());
  data._encounters={3};data.Revert(nullptr);assert(data._encounters.empty()&&data._data.empty());
  stream.bytes.pop_back();stream.offset=0;data.Load(&stream,version,static_cast<uint32_t>(stream.bytes.size()));
  assert(data._data.empty()); // truncated records do not leave a partially loaded registry
 }
 // Reject an invalid tag and oversized string before allocating its payload.
 SKSE::SerializationInterface bad;for(size_t n=0;n<ActorStats::Total;++n)bad.WriteRecordData(0.f);
 bad.WriteRecordData(size_t{1});stl::write_string(&bad,string("k"));bad.WriteRecordData(uint32_t{9});
 remaining=static_cast<uint32_t>(bad.bytes.size());bool threw=false;
 try{ActorStats invalid{&bad,2,remaining};}catch(const runtime_error&){threw=true;}assert(threw);
 SKSE::SerializationInterface huge;for(size_t n=0;n<ActorStats::Total;++n)huge.WriteRecordData(0.f);
 huge.WriteRecordData(size_t{1});huge.WriteRecordData(size_t(-1));
 remaining=static_cast<uint32_t>(huge.bytes.size());threw=false;
 try{ActorStats invalid{&huge,1,remaining};}catch(const runtime_error&){threw=true;}assert(threw);
'''
code += '}\n'
with tempfile.TemporaryDirectory(prefix='registry-serialization-') as directory:
    source_file, binary = Path(directory) / 'test.cpp', Path(directory) / 'test'
    source_file.write_text(code, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++23', str(source_file), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: v2 scalar payload, measured-v1 writer compatibility, unresolved-entry consumption, session reset and truncated/tag/string validation.')
