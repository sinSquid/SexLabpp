"""Actual SharedSnapshot header: final-owner destruction may reenter the slot."""
import os
from pathlib import Path
from source_regressions import ROOT, run

header = Path(os.environ.get('SNAPSHOT_SOURCE', ROOT/'src/Util/SharedSnapshot.h')).read_text()
code = r'''
#include <cassert>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <future>
''' + header + r'''
struct Item {
 int id;
 std::function<void()> onDestroy;
 explicit Item(int value):id(value){}
 ~Item(){if(onDestroy)onDestroy();}
};
int main() {
 Util::SharedSnapshot<Item> slot;
 auto old=std::make_shared<Item>(1);
 bool released=false;
 old->onDestroy=[&] {
  const auto current=slot.load();
  assert(current&&current->id==2);
  released=true;
 };
 slot.store(old);old.reset();
 auto replacement=std::make_shared<Item>(2);
 auto work=std::async(std::launch::async,[&]{slot.store(replacement);});
 if(work.wait_for(std::chrono::seconds(2))!=std::future_status::ready) std::_Exit(10);
 work.get();assert(released);
 auto reader=slot.load();
 replacement->onDestroy=[&]{assert(!slot.load());};
 replacement.reset();slot.store(nullptr);
 assert(reader&&reader->id==2);reader.reset();
}
'''
run('shared_snapshot_release', code)
print('PASS: real SharedSnapshot releases the previous owner outside its mutex and preserves reader ownership')
