"""Exercise the real atomic file writer, including concurrent publishers."""
import os
from pathlib import Path

from source_regressions import ROOT, function, run


baseline = Path(os.environ.get('REVIEW_BASE_DIR', ROOT))
header = baseline / 'src/Util/SaveQueue.h'
case = os.environ.get('REVIEW_CASE', 'all')
if case not in ('all', 'ownership', 'concurrency', 'settings', 'constructor'):
    raise ValueError(f'Unknown REVIEW_CASE: {case}')

code = r'''
#include <algorithm>
#include <barrier>
#include <cassert>
#include <chrono>
#include <iostream>
#include <iterator>
#include <set>
namespace logger {
    template<class... T>void info(T&&...){}
    template<class... T>void error(T&&...){}
}
'''
code += '#include "' + header.as_posix() + '"\n'
code += r'''
std::string read(const std::filesystem::path& path) {
    std::ifstream file(path,std::ios::binary);
    assert(file.is_open());
    return std::string(std::istreambuf_iterator<char>(file),{});
}
void write(const std::filesystem::path& path,const std::string& value) {
    std::ofstream file(path,std::ios::binary);
    file.exceptions(std::ios::badbit|std::ios::failbit);
    file<<value;
}
std::set<std::filesystem::path> entries(const std::filesystem::path& directory) {
    std::set<std::filesystem::path> result;
    for(const auto& entry:std::filesystem::directory_iterator(directory))result.insert(entry.path().filename());
    return result;
}
void ownership(const std::filesystem::path& directory) {
    const auto path=directory/"config.yaml";
    write(path,"previous complete snapshot");
    // A stale or unrelated legacy temporary file must not be opened or deleted.
    const auto foreign=std::filesystem::path(path.string()+".tmp");
    write(foreign,"another writer's bytes");
    // The new writer must skip occupied directory and file reservations too.
    const auto reservation=std::filesystem::path(path.string()+".tmp-0");
    std::filesystem::create_directory(reservation);
    write(reservation/"keep","reserved elsewhere");
    const auto reservedFile=std::filesystem::path(path.string()+".tmp-1");
    write(reservedFile,"also reserved elsewhere");
    const auto before=entries(directory);
    Util::AtomicWrite(path,"published");
    assert(read(path)=="published");
    assert(std::filesystem::exists(foreign));
    assert(read(foreign)=="another writer's bytes");
    assert(read(reservation/"keep")=="reserved elsewhere");
    assert(read(reservedFile)=="also reserved elsewhere");
    assert(entries(directory)==before);

    // Publishing a file over an occupied directory must fail without removing
    // its contents or a temporary file owned by another call.
    const auto blocked=directory/"blocked.yaml";
    std::filesystem::create_directory(blocked);
    write(blocked/"keep","old destination");
    const auto blockedForeign=std::filesystem::path(blocked.string()+".tmp");
    write(blockedForeign,"keep on failure");
    const auto beforeFailure=entries(directory);
    bool failed=false;
    try { Util::AtomicWrite(blocked,"replacement"); } catch(const std::exception&) { failed=true; }
    assert(failed && read(blocked/"keep")=="old destination");
    assert(read(blockedForeign)=="keep on failure");
    assert(entries(directory)==beforeFailure);
    std::cout<<"PASS: exclusive temporary ownership, occupied reservations and failed replacement cleanup\n";
}
void concurrency(const std::filesystem::path& directory) {
    const auto path=directory/"parallel.yaml";
    constexpr int count=8;
    std::vector<std::string> payloads;
    for(int writer=0;writer<count;++writer)payloads.emplace_back(16384*(writer+1),char('A'+writer));
    std::atomic<int> errors=0;
    int corrupt=0;
    for(int trial=0;trial<24;++trial) {
        std::barrier ready(count);
        std::vector<std::thread> writers;
        for(int index=0;index<count;++index)writers.emplace_back([&,index]{
            ready.arrive_and_wait();
            try { Util::AtomicWrite(path,payloads[index]); } catch(const std::exception&) { ++errors; }
        });
        for(auto& writer:writers)writer.join();
        const auto actual=read(path);
        if(std::ranges::find(payloads,actual)==payloads.end())++corrupt;
    }
    assert(errors.load()==0 && corrupt==0);
    for(const auto& entry:std::filesystem::directory_iterator(directory))
        assert(!entry.path().filename().string().starts_with("parallel.yaml.tmp"));
    std::cout<<"PASS: 192 concurrent real atomic writes preserve whole snapshots without collisions\n";
}
int main() {
    const auto directory=std::filesystem::temp_directory_path()/("sexlab-atomic-test-"+
        std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    std::filesystem::create_directory(directory);
    if(CHECK_OWNERSHIP)ownership(directory);
    if(CHECK_CONCURRENCY)concurrency(directory);
    std::filesystem::remove_all(directory);
}
'''
code = code.replace('CHECK_OWNERSHIP', str(case in ('all', 'ownership')).lower())
code = code.replace('CHECK_CONCURRENCY', str(case in ('all', 'concurrency')).lower())
if case in ('all', 'ownership', 'concurrency'):
    run('full7_persistence', code)

code = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
#include <map>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>
namespace logger {
    template<class... T>void info(T&&...){}
    template<class... T>void warn(T&&...){}
    template<class... T>void error(T&&...){}
}
namespace fs { bool exists(const char*){return true;} }
constexpr const char* INIPATH="test.ini";
struct CSimpleIniA {
    static inline std::map<std::string,double> values;
    void SetUnicode(){} int LoadFile(const char*){return 0;}
    const char* GetValue(const char*,const char* key){return values.contains(key)?"configured":nullptr;}
    long GetLongValue(const char*,const char* key){return static_cast<long>(values.at(key));}
    double GetDoubleValue(const char*,const char* key){return values.at(key);}
};
struct Settings {
    static void InitializeINI();
#define INI_SETTING(NAME, DEFAULT, CATEGORY) static inline decltype(DEFAULT) NAME=DEFAULT;
'''
config = (baseline / 'src/UserData/config.def').as_posix()
code += '#include "' + config + '"\n#undef INI_SETTING\n};\n'
code += function((baseline / 'src/UserData/Settings.cpp').read_text(), 'void Settings::InitializeINI()').replace(
    '"config.def"', '"' + config + '"')
code += r'''
struct Random {
    static inline std::vector<std::pair<float,float>> intervals;
    template<class T>static T draw(T low,T high) {
        intervals.emplace_back(low,high);
        assert(std::isfinite(low) && std::isfinite(high) && low<=high);
        // Take the non-Bi relationship branch deterministically; record and
        // validate production distribution arguments without copying its logic.
        return low==0 && high==99 ? high : low+(high-low)/2;
    }
};
namespace RE {
    struct NPC;
    struct BGSRelationship {
        enum class RELATIONSHIP_LEVEL {kLover};
        struct Level {bool all(RELATIONSHIP_LEVEL)const{return true;}} level;
        NPC* npc1;NPC* npc2;
    };
    struct NPC {
        int sex{};std::vector<BGSRelationship*>* relationships{};
        int GetSex(){return sex;}
    };
    struct Actor {NPC* base;NPC* GetActorBase(){return base;}bool IsPlayerRef(){return false;}};
}
namespace Registry {
    enum class Sexuality {None,Hetero,Homo,Bi};
    namespace Statistics {
        struct ActorStats {
            enum StatisticID {Sexuality,Total};
            ActorStats(RE::Actor* owner);
            std::vector<float> _stats;
        };
'''
code += function((baseline / 'src/Registry/Stats.cpp').read_text(), 'ActorStats::ActorStats(RE::Actor* owner)')
code += r'''
    }
}
void checkSettings() {
    const auto initialize=[](double hetero,double homo){
        CSimpleIniA::values={{"fPercentageHetero",hetero},{"fPercentageHomo",homo}};
        Settings::InitializeINI();
        const auto a=Settings::fPercentageHetero,b=Settings::fPercentageHomo;
        assert(std::isfinite(a) && std::isfinite(b) && a>=0 && b>=0);
        assert(a<=100 && b<=100.0f-a);
    };
    for(auto value:{-1.0,std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
        initialize(value,9);assert(Settings::fPercentageHetero==80 && Settings::fPercentageHomo==9);
        initialize(80,value);assert(Settings::fPercentageHetero==80 && Settings::fPercentageHomo==9);
    }
    initialize(0,0);assert(Settings::fPercentageHetero==0 && Settings::fPercentageHomo==0);
    initialize(80,0.5);assert(Settings::fPercentageHetero==80 && Settings::fPercentageHomo==0.5);
    initialize(200,100);
    assert(std::abs(Settings::fPercentageHetero-200.0f/3)<0.00001f);
    assert(std::abs(Settings::fPercentageHomo-100.0f/3)<0.00001f);
    const auto maximum=std::numeric_limits<float>::max();
    initialize(maximum,maximum);
    assert(Settings::fPercentageHetero==50 && Settings::fPercentageHomo==50);
    for(int index=1;index<1000;++index)initialize(index*37.1f,index*0.07f);
    std::cout<<"PASS: production INI percentages reject invalid values and normalize large finite totals safely\n";
}
void checkConstructor() {
    RE::NPC first{1},sameSex{1},otherSex{0};
    RE::BGSRelationship same{{},&first,&sameSex},opposite{{},&first,&otherSex};
    std::vector<RE::BGSRelationship*> relationships{&same};
    first.relationships=&relationships;RE::Actor actor{&first};
    Settings::fPercentageHetero=80;
    for(float value:{0.0f,0.5f,9.0f}) {
        Settings::fPercentageHomo=value;Random::intervals.clear();
        Registry::Statistics::ActorStats stats(&actor);
        assert(Random::intervals.size()==2);
        const auto [low,high]=Random::intervals.back();assert(low==0 && high==value);
        assert(stats._stats.front()>=0 && stats._stats.front()<=value);
    }
    // Mixed relationships select Bi directly, including its collapsed range.
    relationships.push_back(&opposite);
    for(auto percentages:std::array<std::array<float,2>,3>{{{100,0},{90,10},{0,100}}}) {
        Settings::fPercentageHetero=percentages[0];Settings::fPercentageHomo=percentages[1];
        Random::intervals.clear();Registry::Statistics::ActorStats stats(&actor);
        assert(Random::intervals.size()==1);
        assert(stats._stats.front()==percentages[1]);
    }
    std::cout<<"PASS: production statistics constructor receives valid zero, sub-unit and collapsed random intervals\n";
}
int main(){
    if(CHECK_SETTINGS)checkSettings();
    if(CHECK_CONSTRUCTOR)checkConstructor();
}
'''
code = code.replace('CHECK_SETTINGS', str(case in ('all', 'settings')).lower())
code = code.replace('CHECK_CONSTRUCTOR', str(case in ('all', 'constructor')).lower())
if case in ('all', 'settings', 'constructor'):
    run('full7_statistics_configuration', code)
