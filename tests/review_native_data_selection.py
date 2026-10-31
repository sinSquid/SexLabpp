"""Symmetric position compatibility and exhaustive voice lookup contracts."""
from review_native_data_core import fragment, tags
from review_native_data_support import function, run

similar = fragment[:fragment.index('int main()')]
similar = similar.replace('PapyrusSex GetSexPapyrus() const;',
                          'PapyrusSex GetSexPapyrus() const; bool CanFillPosition(const ActorFragment&)const; bool CanFillPosition(const PositionInfo&)const;')
similar += '\nnamespace Registry {\n'
similar += function('src/Registry/Define/Animation.cpp','bool PositionInfo::CanFillPosition(const ActorFragment&')
similar += function('src/Registry/Define/Animation.cpp','bool PositionInfo::CanFillPosition(const PositionInfo&')
similar += r'''
struct Library {Scene scene;static Library* GetSingleton(){static Library v;return &v;}
 const Scene* ReadScene(const std::string&){return &scene;}};
}
namespace RE {struct StaticFunctionTag{};}
#define STATICARGS VM* a_vm, StackID a_stackID, RE::StaticFunctionTag*
#define SCENE(ret) const auto scene=Registry::Library::GetSingleton()->ReadScene(a_id);if(!scene)return ret;
'''
similar += function('src/Papyrus/SexLabRegistry.cpp','bool IsSimilarPosition(')
similar += r'''
int main(){
 using namespace Registry;VM vm;
 ActorFragment male({Sex::Male},RaceKey::Human,1,false,false,false);
 ActorFragment female({Sex::Female},RaceKey::Human,1,false,false,false);
 Library::GetSingleton()->scene.positions={{male},{female},{male}};
 assert(!IsSimilarPosition(&vm,0,nullptr,"scene",0,1));
 assert(!IsSimilarPosition(&vm,0,nullptr,"scene",1,0));
 assert(IsSimilarPosition(&vm,0,nullptr,"scene",0,2));
}
'''

voices = tags[:tags.index('int main()')] + r'''
namespace RE {struct StaticFunctionTag{};}
namespace Registry {
struct Voice{std::string id;bool enabled;TagData tags;std::string GetId()const{return id;}};
struct Library{std::vector<Voice> voices;static Library* GetSingleton(){static Library v;return &v;}
 void ForEachVoice(std::function<bool(const Voice&)> visit){for(auto& v:voices)if(visit(v))return;}};
}
'''
voices += function('src/Papyrus/sslObject/sslVoiceSlots.cpp','std::vector<RE::BSFixedString> GetVoicesByTagsA(')
voices += r'''
int main(){
 using namespace Registry;auto& all=Library::GetSingleton()->voices;
 all={{"one",true,TagData(std::vector<std::string>{"Male","Soft"})},
      {"two",true,TagData(std::vector<std::string>{"Female","Soft"})},
      {"disabled",false,TagData(std::vector<std::string>{"Soft"})},
      {"other",true,TagData(std::vector<std::string>{"Loud"})}};
 assert((GetVoicesByTagsA(nullptr,{"Soft"})==std::vector<std::string>{"one","two"}));
 assert((GetVoicesByTagsA(nullptr,{"Soft","-Male"})==std::vector<std::string>{"two"}));
 assert((GetVoicesByTagsA(nullptr,{"~Soft","~Loud"})==std::vector<std::string>{"one","two","other"}));
}
'''

if __name__ == '__main__':
    run('symmetric_position_compatibility',similar)
    run('all_matching_voices',voices)
