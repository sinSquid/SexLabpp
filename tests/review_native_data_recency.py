"""Encounter-type recency must survive unrelated later encounters."""
import statistics_roundtrip as fixture
from review_native_data_support import run

captured = []
original_run = fixture.run
try:
    fixture.run = lambda name, code: captured.append(code)
    fixture.statistics_test()
finally:
    fixture.run = original_run
code = captured[0].split('int main() {', 1)[0]
# All events occur at the same game timestamp: float equality must not lose ordering.
code = code.replace('return ++time;', 'return time;')
code = code.replace('std::vector<char> bytes; size_t pos=0;',
                    'std::vector<char> bytes; size_t pos=0; size_t failAfter=SIZE_MAX; std::map<uint32_t,uint32_t> remap;')
code = code.replace('auto k=std::min<size_t>(n,bytes.size()-pos);',
                    'if(pos+n>failAfter)return 0; auto k=std::min<size_t>(n,bytes.size()-pos);')
code = code.replace('resolved=old;return old!=99;',
                    'resolved=remap.contains(old)?remap.at(old):old;return old!=99&&resolved!=0;')
code += r'''
int main(){
 using namespace Registry::Statistics;
 using Type=ActorEncounter::EncounterType;
 RE::Actor a(1),b(2),c(3);
 auto* stats=StatisticsData::GetSingleton();
 stats->AddEncounter(&a,&b,Type::Victim);
 stats->AddEncounter(&a,&c,Type::Victim);
 stats->AddEncounter(&a,&b,Type::Any);
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&c);
 assert(stats->GetMostRecentEncounter(&a,Type::Submissive)==&c);
 assert(stats->GetMostRecentEncounter(&a,Type::Any)==&b);
 assert(stats->GetMostRecentEncounter(&b,Type::Aggressor)==&a);
 assert(stats->GetMostRecentEncounter(&a,Type::Aggressor)==nullptr);

 SKSE::SerializationInterface data,recency;
 stats->Save(&data);stats->SaveEncounterRecency(&recency);
 const auto restore=[&](bool reverse,bool extra){
  stats->Revert(nullptr);stats->BeginLoad();data.pos=recency.pos=0;
  if(reverse&&extra)stats->LoadEncounterRecency(&recency,static_cast<uint32_t>(recency.bytes.size()));
  stats->Load(&data,2,static_cast<uint32_t>(data.bytes.size()));
  if(!reverse&&extra)stats->LoadEncounterRecency(&recency,static_cast<uint32_t>(recency.bytes.size()));
  stats->FinishLoad();
 };
 for(bool reverse:{false,true}){
  restore(reverse,true);
  assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&c);
  assert(stats->GetMostRecentEncounter(&a,Type::Any)==&b);
  assert(stats->GetEncounter(&a,&b)->GetTimesMet()==2);
  assert(stats->GetEncounter(&a,&b)->GetTimesVictim(1)==1);
 }
 // Existing stcs v2 payload is unchanged: no extra bytes are appended to it.
 SKSE::SerializationInterface after;stats->Save(&after);assert(after.bytes==data.bytes);
 restore(false,false);
 // Old saves only have the pair's last-any order: preserve the explicitly
 // documented estimate, then record exact new typed events from here onward.
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&b);
 assert(stats->GetEncounter(&a,&b)->GetTimesMet()==2);
 stats->AddEncounter(&a,&c,Type::Victim);stats->AddEncounter(&a,&b,Type::Any);
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&c);

 // A cut record rejects atomically without clearing the existing statistics.
 auto truncated=recency;truncated.bytes.pop_back();truncated.pos=0;
 restore(false,false);stats->BeginLoad();
 stats->LoadEncounterRecency(&truncated,static_cast<uint32_t>(truncated.bytes.size()));stats->FinishLoad();
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&b);
 assert(stats->GetEncounter(&a,&b)->GetTimesMet()==2);
 // A stream that fails after reading the first entry also publishes nothing;
 // an already accepted complete record remains intact.
 stats->BeginLoad();recency.pos=0;stats->LoadEncounterRecency(&recency,static_cast<uint32_t>(recency.bytes.size()));
 auto failed=recency;failed.pos=0;failed.failAfter=8+40+4;
 stats->LoadEncounterRecency(&failed,static_cast<uint32_t>(failed.bytes.size()));stats->FinishLoad();
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&c);

 RE::Actor mappedA(101),mappedB(102),mappedC(103);
 data.remap=recency.remap={{1,101},{2,102},{3,103}};restore(true,true);
 assert(stats->GetMostRecentEncounter(&mappedA,Type::Victim)==&mappedC);
 assert(!stats->GetEncounter(&a,&b));
 data.remap=recency.remap={{1,101},{2,102},{3,0}};restore(false,true);
 assert(stats->GetMostRecentEncounter(&mappedA,Type::Victim)==&mappedB);
 assert(!stats->GetEncounter(&mappedA,&mappedC));
 data.remap.clear();recency.remap.clear();

 // Pending records cannot survive actor deletion or Revert into newly created encounters.
 for(bool revert:{false,true}){
  restore(false,true);stats->BeginLoad();recency.pos=0;
  stats->LoadEncounterRecency(&recency,static_cast<uint32_t>(recency.bytes.size()));
  if(revert)stats->Revert(nullptr);else stats->DeleteStatistics(a.GetFormID());
  stats->AddEncounter(&a,&c,Type::Victim);stats->AddEncounter(&a,&b,Type::Victim);stats->FinishLoad();
  assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&b);
 }

 // Untrusted maximum order values do not wrap the next real encounter to zero.
 restore(false,false);SKSE::SerializationInterface maxOrder;
 Util::WriteRecord(&maxOrder,uint64_t{2});
 for(uint32_t partner:{2u,3u}){
  Util::WriteRecord(&maxOrder,uint32_t{1});Util::WriteRecord(&maxOrder,partner);
  const uint64_t order=UINT64_MAX-(partner==3);
  for(auto value:std::array<uint64_t,4>{order,0,order,0})Util::WriteRecord(&maxOrder,value);
 }
 stats->BeginLoad();stats->LoadEncounterRecency(&maxOrder,static_cast<uint32_t>(maxOrder.bytes.size()));stats->FinishLoad();
 stats->AddEncounter(&a,&c,Type::Victim);stats->AddEncounter(&a,&b,Type::Any);
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&c);
 stats->Revert(nullptr);stats->AddEncounter(&a,&a,Type::Victim);
 assert(stats->GetMostRecentEncounter(&a,Type::Victim)==&a);
 std::cout<<"PASS: exact type order, new record roundtrip/order, v2 fallback, truncation, resolution, cleanup and overflow\n";
}
'''
if __name__ == '__main__': run('encounter_recency',code)
