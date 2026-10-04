"""Production hysteresis and snapshot functions with deterministic descriptor inputs."""
from source_regressions import ROOT, function, run

source=(ROOT/'src/Thread/NiNode/NiInstance.cpp').read_text()
code=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <vector>
namespace RE { using FormID=unsigned;using ActorPtr=int; }
namespace Registry { enum class Sex { Male }; }
namespace Settings { inline float fEnterThreshold=.7f,fExitThreshold=.3f; }
namespace Thread::NiNode {
namespace NiType { enum class Type{None,Vaginal,Kissing};enum class Cluster{None,Crotch,Head,KissingCl}; }
namespace NiMath { float Sigmoid(float value){return value;} }
struct Descriptor { NiType::Type type;float probability; float Predict()const{return probability;} };
struct NiInteraction {
 std::unique_ptr<Descriptor> descriptor;float velocity=0,timeActive=0;bool active=false;
 NiType::Type GetType()const{return descriptor->type;}
};
struct NiInteractionCluster {
 std::vector<NiInteraction> interactions;
 bool IsBinary()const{return interactions.size()==1;}
 bool IsSoftmax()const{return interactions.size()>1;}
 NiInteraction* ApplySoftmax(){return nullptr;}
};
struct Motion{bool HasSufficientData()const{return true;}};
struct NiActor{Motion motion;const auto& Motion()const{return motion;}bool IsSex(Registry::Sex)const{return true;}bool operator==(const NiActor& rhs)const{return this==&rhs;}};
float probability=.8f;bool visible=true;
NiInteractionCluster EvaluateCrotchInteractions(const Motion&,const Motion&){
 NiInteractionCluster result;if(visible)result.interactions.push_back({std::make_unique<Descriptor>(Descriptor{NiType::Type::Vaginal,probability}),2});return result;
}
NiInteractionCluster EvaluateHeadInteractions(const Motion&,const Motion&){return {};}
NiInteractionCluster EvaluateKissingCluster(const Motion&,const Motion&){return {};}
struct NiInstance {
 struct InteractionSnapshot {NiType::Type type;float velocity;NiType::Type GetType()const{return type;}};
 struct PairInteractionState{std::array<NiInteractionCluster,4> interactionClusters;float lastUpdateTime=0;};
 PairInteractionState state;
 void EvaluateRuleBased(PairInteractionState&,const NiActor&,const NiActor&)const;
 void UpdateHysteresis(PairInteractionState&,float);
 std::vector<InteractionSnapshot> GetInteractions(RE::FormID,RE::FormID,NiType::Type)const;
 void ForEachInteraction(const std::function<void(RE::ActorPtr,RE::ActorPtr,const NiInteraction&)>& f,RE::FormID,RE::FormID,NiType::Type)const {
  for(const auto& cluster:state.interactionClusters)for(const auto& interaction:cluster.interactions)f(0,0,interaction);
 }
};
'''
for signature in ('void NiInstance::EvaluateRuleBased','void NiInstance::UpdateHysteresis','std::vector<NiInstance::InteractionSnapshot> NiInstance::GetInteractions'):
 code+=function(source,signature)+'\n'
code+=r'''
}
int main(){using namespace Thread::NiNode;
 NiInstance instance;NiActor actor;
 auto step=[&](float p,float time){probability=p;instance.EvaluateRuleBased(instance.state,actor,actor);instance.UpdateHysteresis(instance.state,time);instance.state.lastUpdateTime=time;};
 step(.8f,1);auto snapshot=instance.GetInteractions(0,0,NiType::Type::None);assert(snapshot.size()==1);
 step(.5f,2);assert(instance.GetInteractions(0,0,NiType::Type::None).size()==1);assert(instance.state.interactionClusters[1].interactions[0].timeActive==1);
 step(.2f,3);assert(instance.GetInteractions(0,0,NiType::Type::None).empty());
 assert(snapshot[0].GetType()==NiType::Type::Vaginal && snapshot[0].velocity==2);
 step(.5f,4);assert(instance.GetInteractions(0,0,NiType::Type::None).empty());
 visible=false;step(.8f,5);assert(instance.state.interactionClusters[1].interactions.empty());
 visible=true;step(.5f,6);assert(instance.GetInteractions(0,0,NiType::Type::None).empty());
 std::cout<<"PASS: production multi-frame hysteresis, disappearing types, immutable query snapshots\n";
}
'''
run('recognition',code)
