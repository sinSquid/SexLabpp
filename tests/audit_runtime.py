"""Production lock ownership, bounded work and world-grid traversal regressions."""
from source_regressions import ROOT, function, run

run('locked_access_and_work', r'''
#include <cassert>
#include <chrono>
#include <future>
#include <memory>
#include <shared_mutex>
#include <stdexcept>
#include "Util/LockedAccess.h"
#include "Util/FileWork.h"
using namespace std::chrono_literals;
int main(int, char** argv) {
    std::recursive_mutex mutex;
    auto object = std::make_unique<int>(7);
    using Access = Util::LockedAccess<int, std::unique_lock<std::recursive_mutex>>;
    std::promise<bool> tried;
    std::future<void> destroy;
    {
        Access first{std::unique_lock{mutex}, object.get()};
        Access nested{std::unique_lock{mutex}, object.get()};
        Access moved{std::move(first)}; assert(!first && *moved==7 && nested.get()==object.get());
        destroy = std::async(std::launch::async, [&] {
            const bool available = mutex.try_lock();
            tried.set_value(available);
            if (available) mutex.unlock();
            std::lock_guard guard{mutex}; object.reset();
        });
        assert(!tried.get_future().get());
        assert(destroy.wait_for(10ms)==std::future_status::timeout);
        assert(*moved==7);
    }
    destroy.get(); assert(!object);
    std::array<std::atomic_int, 100> counts{};
    std::atomic_int active{}, peak{};
    try {
        Util::ForEachBounded(counts.size(), [&](size_t i) {
            const int current=++active;
            int old=peak.load();while(old<current&&!peak.compare_exchange_weak(old,current)){}
            ++counts[i];--active;
            if(i==5)throw std::runtime_error("expected");
        }, 3);
        assert(false);
    } catch(const std::runtime_error&) {}
    for(auto& count:counts)assert(count==1);
    assert(peak<=3 && active==0);
    Util::ForEachBounded(0, [](size_t){assert(false);});
    const auto missing=Util::ListFiles(std::string(argv[1])+".missing",true);
    assert(missing.files.empty()&&missing.error);
}
''')

source = (ROOT / 'src/Util/World.h').read_text()
run('world_grid', r'''
#include <cassert>
#include <cstdint>
#include <functional>
#include <vector>
namespace RE {
struct BSContainer {enum class ForEachResult {kContinue};};
struct Point {float x,y,z;};
struct TESObjectREFR {Point position;Point GetPosition(){return position;}};
struct Cell {
    struct Coordinates {float worldX,worldY;} coords{};
    bool attached=true;int visits=0;
    bool IsAttached(){return attached;} Coordinates* GetCoordinates(){return &coords;}
    void ForEachReferenceInRange(Point,float,const std::function<BSContainer::ForEachResult(TESObjectREFR*)>&){++visits;}
};
struct Grid {uint32_t length=3;Cell cells[3][3];Cell* GetCell(uint32_t x,uint32_t y){return &cells[x][y];}};
struct TES {Cell* interiorCell=nullptr;Grid* gridCells=nullptr;static TES* GetSingleton(){static TES v;return &v;}};
}
''' + function(source, 'inline void ForEachObjectInRange(') + r'''
int main(){
 RE::Grid grid;for(unsigned x=0;x<3;++x)for(unsigned y=0;y<3;++y)grid.cells[x][y].coords={x*4096.f,y*4096.f};
 RE::TES::GetSingleton()->gridCells=&grid;RE::TESObjectREFR center{{6000,6000,0}};
 auto visit=[](RE::TESObjectREFR*){return RE::BSContainer::ForEachResult::kContinue;};
 ForEachObjectInRange(&center,9000,visit);
 for(auto& row:grid.cells)for(auto& cell:row)assert(cell.visits==1);
 RE::Cell interior;RE::TES::GetSingleton()->interiorCell=&interior;
 ForEachObjectInRange(&center,9000,visit);assert(interior.visits==1);
 for(auto& row:grid.cells)for(auto& cell:row)assert(cell.visits==1);
}
''')
