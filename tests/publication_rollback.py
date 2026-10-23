"""Inject allocation failure at every allocation in the actual publication helper."""
from source_regressions import run
run('publication_rollback',r'''
#include <cassert>
#include <cstdlib>
#include <map>
#include <new>
#include <unordered_map>
#include "Util/PublishPackage.h"
long remaining=-1;
void* operator new(size_t size){
 if(remaining==-2)throw std::bad_alloc();
 if(remaining>=0&&remaining--==0){remaining=-2;throw std::bad_alloc();}
 if(auto p=std::malloc(size?size:1))return p;
 throw std::bad_alloc();
}
void operator delete(void* p)noexcept{std::free(p);}
void operator delete(void* p,size_t)noexcept{std::free(p);}
struct Scene{int id;};
struct Package{std::vector<std::unique_ptr<Scene>> scenes;};
int main(){
 bool completed=false;int failures=0;
 for(int failure=0;failure<100&&!completed;++failure){
  std::vector<std::unique_ptr<Package>> packages;
  auto old=std::make_unique<Package>();old->scenes.push_back(std::make_unique<Scene>(Scene{7}));
  auto* oldScene=old->scenes[0].get();auto* oldPackage=old.get();packages.push_back(std::move(old));
  std::map<int,Scene*> ids{{7,oldScene}};
  std::unordered_map<Scene*,const Package*> owners{{oldScene,oldPackage}};
  std::unordered_map<int,std::vector<Scene*>> index{{11,{oldScene}}};
  owners.max_load_factor(.5f);owners.rehash(2);
  index.max_load_factor(.5f);index.rehash(2);
  const auto buckets=owners.bucket_count();
  auto pending=std::make_unique<Package>();
  for(int id:{7,7,8})pending->scenes.push_back(std::make_unique<Scene>(Scene{id}));
  auto* a=pending->scenes[0].get();auto* b=pending->scenes[1].get();auto* c=pending->scenes[2].get();
  std::vector<std::pair<int,Scene*>> changes{{11,a},{22,a},{22,a},{11,b},{33,c}};
  const auto beforeIds=ids;const auto beforeOwners=owners;const auto beforeIndex=index;
  remaining=failure;
  try{Util::PublishPackage(pending,packages,ids,owners,index,changes);completed=true;}
  catch(const std::bad_alloc&){++failures;}
  remaining=-1;
  if(!completed){assert(pending&&packages.size()==1);assert(ids==beforeIds&&owners==beforeOwners&&index==beforeIndex);}
  else{assert(!pending&&packages.size()==2&&ids.at(7)==b&&ids.at(8)==c);assert(index.at(22)==std::vector<Scene*>{a});assert(owners.bucket_count()>buckets);}
 }
 assert(completed&&failures>10);
}
''')
