#include "Thread.h"

#include "Registry/Library.h"
#include "Registry/Util/RayCast/Offsets.h"
#include "Thread/Hooks.h"
#include "Thread/Interface/FurnSelectMenu.h"
#include "Thread/Interface/SceneHUD.h"
#include "Thread/Interface/StageSelectMenu.h"
#include "Util/Script.h"

namespace Thread
{
    void Instance::Revert()
    {
        decltype(instances) releasedInstances;
        decltype(pendingInstances) releasedPending;
        {
            const std::unique_lock lock{ _mInstances };
            worldGeneration.fetch_add(1);
            for (auto& [quest, cancelled] : creatingInstances)
                cancelled->store(true);
            for (auto& instance : instances)
                instance->creationCancelled->store(true);
            for (auto& instance : pendingInstances)
                instance->creationCancelled->store(true);
            creatingInstances.clear();
            releasedInstances.swap(instances);
            releasedPending.swap(pendingInstances);
        }
        // Destruction/ref release is outside registry locks. Never restore the old world.
        NiNode::NiUpdate::Revert();
        LegacyNiNode::NiUpdate::Revert();
        DiscardPreparedActors();
        Interface::SceneHUD::GetSingleton().Destroy();
        Interface::FurnSelectMenu::GetSingleton().Revert();
        Interface::StageSelectMenu::GetSingleton().Revert();
        Hooks::SetWeaponDrawBlocked(false);
    }

    void Instance::CreateInstance(RE::TESQuest* a_linkedQst, const std::vector<RE::Actor*>& a_submissives, const SceneMapping& a_scenes, FurniturePreference a_furniturePreference, int32_t a_request)
    {
        const auto generation = GetWorldGeneration();
        const auto script = Script::GetScriptObject(a_linkedQst, "sslThreadModel");
        const auto request = script ? script->GetProperty("StartupRequest") : nullptr;
        if (!request || RE::BSScript::UnpackValue<int32_t>(request) != a_request)
            return;
        const auto cancelled = std::make_shared<std::atomic_bool>(false);
        bool alreadyCreating;
        {
            std::unique_lock lock{ _mInstances };
            if (RE::BSScript::UnpackValue<int32_t>(request) != a_request)
                return;
            alreadyCreating = creatingInstances.contains(a_linkedQst) ||
                              std::ranges::any_of(instances, [a_linkedQst](const auto& instance) { return instance->linkedQst == a_linkedQst; }) ||
                              std::ranges::any_of(pendingInstances, [a_linkedQst](const auto& instance) { return instance->linkedQst == a_linkedQst; });
            if (!alreadyCreating)
                creatingInstances.emplace(a_linkedQst, cancelled);
        }
        if (alreadyCreating) {
            logger::warn("Thread instance already exists for quest {:X}.", a_linkedQst->formID);
            DispatchContinueSetup(a_linkedQst, false, a_request);
            return;
        }
        try {
            auto instance = std::make_shared<Instance>(a_linkedQst, a_submissives, a_scenes, a_furniturePreference, a_request, cancelled);
            std::unique_lock lock{ _mInstances };
            const auto creating = creatingInstances.find(a_linkedQst);
            if (cancelled->load() || creating == creatingInstances.end() || creating->second != cancelled) {
                SKSE::GetTaskInterface()->AddTask([a_linkedQst, a_request, generation]() {
                    if (GetWorldGeneration() != generation)
                        return;
                    Interface::FurnSelectMenu::GetSingleton().Cancel(a_linkedQst, a_request);
                });
                return;
            }
            creatingInstances.erase(creating);
            if (instance->pendingQst != nullptr) {
                pendingInstances.emplace_back(instance);
                lock.unlock();
                // Publish before accepting input; build and show the menu on the game thread.
                SKSE::GetTaskInterface()->AddTask([instance]() {
                    if (instance->creationCancelled->load())
                        return;
                    try {
                        instance->ShowCenterRefMenu();
                    } catch (const std::exception& error) {
                        {
                            std::unique_lock pendingLock{ _mInstances };
                            std::erase(pendingInstances, instance);
                        }
                        logger::error("Unable to show center selection menu: {}", error.what());
                        if (!instance->creationCancelled->load())
                            DispatchContinueSetup(instance->linkedQst, false, instance->startupRequest);
                    }
                });
                // DispatchContinueSetup() called by Instance::FinalizeCenterRefSelection()
            } else {
                instances.emplace_back(std::move(instance));
                lock.unlock();
                DispatchContinueSetup(a_linkedQst, true, a_request);
            }
            return;
        } catch (const std::exception& e) {
            {
                std::unique_lock lock{ _mInstances };
                const auto creating = creatingInstances.find(a_linkedQst);
                if (creating != creatingInstances.end() && creating->second == cancelled)
                    creatingInstances.erase(creating);
                std::erase_if(pendingInstances, [a_linkedQst, a_request](const auto& instance) {
                    return instance->linkedQst == a_linkedQst && instance->startupRequest == a_request;
                });
            }
            logger::error("Failed to create thread instance: {}", e.what());
            if (!cancelled->load())
                DispatchContinueSetup(a_linkedQst, false, a_request);
            else
                SKSE::GetTaskInterface()->AddTask([a_linkedQst, a_request, generation]() {
                    if (GetWorldGeneration() != generation)
                        return;
                    Interface::FurnSelectMenu::GetSingleton().Cancel(a_linkedQst, a_request);
                });
            return;
        }
    }

    void Instance::DestroyInstance(RE::TESQuest* a_linkedQst, bool a_preservePreparedActors)
    {
        const auto generation = GetWorldGeneration();
        std::vector<int32_t> cancelledSelections;
        {
            std::unique_lock lock{ _mInstances };
            if (const auto creating = creatingInstances.find(a_linkedQst); creating != creatingInstances.end()) {
                creating->second->store(true);
                creatingInstances.erase(creating);
            }
            std::erase_if(pendingInstances, [&](const auto& instance) {
                if (instance->linkedQst != a_linkedQst)
                    return false;
                instance->creationCancelled->store(true);
                cancelledSelections.push_back(instance->startupRequest);
                return true;
            });
            // Both registries own their entries independently of Thread::Instance.
            LegacyNiNode::NiUpdate::Unregister(a_linkedQst->GetFormID());
            NiNode::NiUpdate::Unregister(a_linkedQst->GetFormID());
            std::erase_if(instances, [&](const auto& instance) {
                if (instance->linkedQst != a_linkedQst) {
                    return false;
                }
                instance->creationCancelled->store(true);
                if (!a_preservePreparedActors && instance->GetPosition(RE::PlayerCharacter::GetSingleton())) {
                    Hooks::SetWeaponDrawBlocked(false);
                }
                instance->niInstance.store(nullptr);
                instance->niInstanceLegacy.store(nullptr);
                instance->ReleaseAnimations();
                return true;
            });
        }
        for (const auto request : cancelledSelections)
            SKSE::GetTaskInterface()->AddTask([a_linkedQst, request, generation]() {
                if (GetWorldGeneration() != generation)
                    return;
                Interface::FurnSelectMenu::GetSingleton().Cancel(a_linkedQst, request);
            });
        if (!a_preservePreparedActors) {
            RestorePreparedActors(a_linkedQst);
        }
    }

    std::shared_ptr<Instance> Instance::GetInstance(RE::TESQuest* a_linkedQst)
    {
        std::shared_lock lock{ _mInstances };
        for (auto&& instance : instances) {
            if (instance->linkedQst == a_linkedQst) {
                return instance;
            }
        }
        return nullptr;
    }

    std::shared_ptr<Instance> Instance::GetPendingInstance(RE::TESQuest* a_linkedQst)
    {
        std::shared_lock lock{ _mInstances };
        for (auto&& instance : pendingInstances) {
            if (instance->linkedQst == a_linkedQst) {
                return instance;
            }
        }
        return nullptr;
    }

    void Instance::DispatchContinueSetup(RE::TESQuest* a_linkedQst, bool a_result, int32_t a_request)
    {
        const auto handle = Script::GetScriptObject(a_linkedQst, "sslThreadModel");
        Script::CallbackPtr callbackPtr{};
        if (!handle || !Script::DispatchMethodCall(handle, "ContinueSetup", callbackPtr, bool{ a_result }, int32_t{ a_request }))
            logger::error("Failed to dispatch startup completion for quest {:X}, request {}.", a_linkedQst->GetFormID(), a_request);
    }

    void Instance::Center::SetReference(RE::TESObjectREFR* a_ref, Registry::FurnitureOffset a_offset)
    {
        assert(alias && a_ref);
        alias->ForceRefTo(a_ref);
        offset = a_offset;
        details = Registry::Library::GetSingleton()->GetFurnitureDetails(a_ref);
    }

    void Instance::AdvanceScene(const Registry::Stage* a_nextStage)
    {
        assert(activeScene && activeScene->GetStageNodeType(a_nextStage) != Registry::Scene::NodeType::None);
        if (Settings::bUseLegacyNiType) {
            if (!HasNiInstanceLegacy()) {
                niInstanceLegacy.store(LegacyNiNode::NiUpdate::Register(linkedQst->formID, *activeAssignment, activeScene));
            }
        } else if (!HasNiInstance()) {
            niInstance.store(NiNode::NiUpdate::Register(linkedQst->formID, *activeAssignment, activeScene));
        }
        fixedLengthTimer.state = FixedLengthTimer::State::Stopped;
        activeStage = a_nextStage;
        ReleaseAnimations();
        pendingAnimations.clear();
        pendingAnimations.reserve(activeAssignment->size());
        for (size_t i = 0; i < activeAssignment->size(); i++) {
            const auto& actor = activeAssignment->at(i);
            const auto& animationEvent = activeScene->GetNthAnimationEvent(a_nextStage, i);

            pendingAnimations.emplace_back(actor, animationEvent, std::vector<ActiveClip>{}, nullptr, std::string{}, 0.0f, 0.0f, 0.0f, i);
        }
        //if (ControlsMenu()) {
        //    Interface::SceneMenu::UpdateStageInfo();
        //}
    }

    void Instance::RealignActors()
    {
        for (size_t i = 0; i < activeAssignment->size(); i++) {
            ReassertPlacement(i, false);
        }
    }

    bool Instance::SetActiveScene(const Registry::Scene* a_scene, bool a_refreshHUD)
    {
        assert(a_scene);
        if (!a_scene->IsCompatibleFurniture(center.offset.type)) {
            logger::warn("Scene {} is not compatible with center reference {}.", a_scene->id, center.GetRef()->GetFormID());
            return false;
        }
        std::vector<Registry::ActorFragment> fragments;
        fragments.reserve(positions.size());
        for (const auto& position : positions)
            fragments.push_back(position.data);
        const auto newAssignments = a_scene->FindAssignments(fragments);
        if (newAssignments.empty()) {
            logger::warn("Scene {} has no valid assignments.", a_scene->id);
            return false;
        }
        CancelFixedLengthTimer();
        UnregisterNiInstance();
        UnregisterNiInstanceLegacy();
        assignments = newAssignments;
        activeScene = a_scene;
        ReleaseAnimations();
        pendingAnimations.clear();
        std::map<RE::Actor*, std::set<size_t>> uniquePositions;
        for (const auto& assignment : assignments) {
            for (size_t i = 0; i < assignment.size(); i++) {
                uniquePositions[assignment[i]].insert(i);
            }
        }
        for (auto&& p : positions) {
            p.uniquePermutations = static_cast<uint8_t>(uniquePositions[p.data.GetActor()].size());
        }
        baseCoordinates = center.offset.offset.ApplyReturn(center.GetRef());
        activeScene->furnitureOffset.Apply(baseCoordinates);
        activeAssignment = assignments.begin();

        if (auto* sceneHUD = a_refreshHUD ? Interface::SceneHUD::GetSingleton().GetForThread(linkedQst) : nullptr)
            sceneHUD->RebuildSceneList();
        return true;
    }

    std::vector<const Registry::Scene*> Instance::GetThreadScenes(SceneType a_type)
    {
        assert(a_type < SceneType::Total);
        return scenes[a_type];
    }

    std::vector<const Registry::Scene*> Instance::GetThreadScenes()
    {
        for (auto&& sceneVec : scenes) {
            if (std::ranges::contains(sceneVec, activeScene)) {
                return sceneVec;
            }
        }
        return {};
    }

    const std::vector<RE::Actor*>& Instance::GetActors()
    {
        assert(activeAssignment != assignments.end());
        return *activeAssignment;
    }

    Instance::Position* Instance::GetPosition(RE::Actor* a_actor)
    {
        assert(a_actor);
        for (auto& position : positions) {
            if (position.data.GetActor() == a_actor) {
                return &position;
            }
        }
        return nullptr;
    }

    const Registry::PositionInfo* Instance::GetPositionInfo(RE::Actor* a_actor)
    {
        assert(a_actor);
        const auto i = std::distance(activeAssignment->begin(), std::find(activeAssignment->begin(), activeAssignment->end(), a_actor));
        assert(i >= 0);
        if (static_cast<size_t>(i) >= activeAssignment->size()) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return nullptr;
        }
        return activeScene->GetNthPosition(i);
    }

    void Instance::UpdatePlacement(RE::Actor* a_actor)
    {
        assert(a_actor);
        const auto i = std::distance(activeAssignment->begin(), std::find(activeAssignment->begin(), activeAssignment->end(), a_actor));
        assert(i >= 0);
        if (static_cast<size_t>(i) >= activeAssignment->size()) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return;
        }
        ReassertPlacement(static_cast<size_t>(i), true);
    }

    void Instance::ReassertPlacement(size_t a_position, bool a_force)
    {
        const auto actor = activeAssignment->at(a_position);
        const auto& position = activeStage->positions[a_position];
        const auto& coordinate = position.offset.ApplyReturn(baseCoordinates);
        constexpr float positionToleranceSquared = 0.25f;
        constexpr float rotationTolerance = 0.008726646f;
        constexpr float fullRotation = 6.283185307f;
        if (!a_force && actor->GetPosition().GetSquaredDistance(coordinate.AsNiPoint()) <= positionToleranceSquared && std::abs(std::remainder(actor->GetAngleZ() - coordinate.rotation, fullRotation)) <= rotationTolerance) {
            return;
        }
        actor->SetAngle({ 0.0f, 0.0f, coordinate.rotation });
        actor->SetPosition(coordinate.AsNiPoint(), true);
        actor->Update3DPosition(true);
    }

    bool Instance::ReplaceCenterRef(RE::TESObjectREFR* a_ref)
    {
        if (((bool (*)(void))Offsets::NotOnGameThread.address())()) {
            logger::error("ReplaceCenterRef is not on valid thread, this should never happen and can cause random CTD/freezes");
        }
        assert(a_ref);
        if (a_ref == center.GetRef() && !a_ref->IsPlayerRef()) {
            return false;
        }
        const auto centerStr = center.offset.type.ToString();
        const auto* details = Registry::Library::GetSingleton()->GetFurnitureDetails(a_ref);
        if (!details) {
            if (!center.offset.type.IsNone()) {
                constexpr auto nonStr = Registry::FurnitureType::ToString<Registry::FurnitureType::None>();
                logger::warn("Mismatched furniture type. Expected {} but got {} for reference {:X}", centerStr, nonStr, a_ref->GetFormID());
                return false;
            }
            center.SetReference(a_ref, {});
        } else {
            const auto inBounds = details->GetClosestCoordinatesInBound(a_ref, center.offset.type.value, center.GetRef());
            if (inBounds.empty()) {
                logger::warn("Reference {:X} is not compatible with any scene.", a_ref->GetFormID());
                return false;
            }
            center.SetReference(a_ref, inBounds.front());
        }
        baseCoordinates = center.offset.offset.ApplyReturn(center.GetRef());
        activeScene->furnitureOffset.Apply(baseCoordinates);
        AdvanceScene(activeStage);
        return true;
    }

    void Instance::OffsetAdjustSet(uint32_t actorFormId, Registry::CoordinateType axis, float value)
    {
        if (!activeScene || !activeStage)
            return;

        // scene/furniture offset
        if (actorFormId == 0) {
            Registry::Library::GetSingleton()->EditScene(activeScene, [&](Registry::Scene* scene) {
                scene->furnitureOffset.SetOffset(value, axis);
            });
            baseCoordinates = center.offset.offset.ApplyReturn(center.GetRef());
            activeScene->furnitureOffset.Apply(baseCoordinates);
            AdvanceScene(activeStage);

            // position offset
        } else {
            const auto it = std::find_if(activeAssignment->begin(), activeAssignment->end(),
                [&](RE::Actor* a) { return a && a->GetFormID() == actorFormId; });
            if (it == activeAssignment->end())
                return;
            const auto posIdx = static_cast<size_t>(std::distance(activeAssignment->begin(), it));

            Registry::Library::GetSingleton()->EditScene(activeScene, [&](Registry::Scene* scene) {
                if (Instance::GetThreadProperty<bool>("VarUI_AdjustStage")) {
                    auto* stage = const_cast<Registry::Stage*>(scene->GetStageByID(activeStage->id));
                    if (stage && posIdx < stage->positions.size())
                        stage->positions[posIdx].offset.SetOffset(value, axis);
                } else {
                    scene->ForEachStage([&](Registry::Stage* st) {
                        if (posIdx < st->positions.size())
                            st->positions[posIdx].offset.SetOffset(value, axis);
                        return false;
                    });
                }
            });
            UpdatePlacement(*it);
        }
    }

    void Instance::OffsetAdjustReset(bool hasFurn)
    {
        if (!activeScene || !activeStage)
            return;
        Registry::Library::GetSingleton()->EditScene(activeScene, [&](Registry::Scene* scene) {
            if (hasFurn) {
                scene->furnitureOffset.ResetOffset();
                baseCoordinates = center.offset.offset.ApplyReturn(center.GetRef());
                scene->furnitureOffset.Apply(baseCoordinates);
            }
            scene->ForEachStage([](Registry::Stage* stage) {
                for (auto&& pos : stage->positions) {
                    pos.offset.ResetOffset();
                }
                return false;
            });
        });
        for (size_t i = 0; i < activeAssignment->size(); i++) {
            ReassertPlacement(i, true);
        }
    }

    const Registry::Expression* Instance::GetExpression(RE::Actor* a_actor)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return nullptr;
        }
        return position->expression;
    }

    void Instance::SetExpression(RE::Actor* a_actor, const Registry::Expression* a_expression)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return;
        }
        position->expression = a_expression;
    }

    const Registry::Voice* Instance::GetVoice(RE::Actor* a_actor)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return nullptr;
        }
        return position->voice;
    }

    void Instance::SetVoice(RE::Actor* a_actor, const Registry::Voice* a_voice)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return;
        }
        position->voice = a_voice;
    }

    int32_t Instance::GetUniquePermutations(RE::Actor* a_actor)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::warn("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return 0;
        }
        return position->uniquePermutations;
    }

    int32_t Instance::GetCurrentPermutation(RE::Actor* a_actor)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::error("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return 0;
        }

        const auto currentPosition = std::distance(activeAssignment->begin(), std::find(activeAssignment->begin(), activeAssignment->end(), a_actor));
        if (currentPosition < 0 || static_cast<size_t>(currentPosition) == activeAssignment->size()) {
            logger::error("Actor {} is not part of the current assignment.", a_actor->GetFormID());
            return 0;
        }

        std::set<ptrdiff_t> uniquePositions;
        for (const auto& assignment : assignments) {
            const auto actorIt = std::find(assignment.begin(), assignment.end(), a_actor);
            if (actorIt == assignment.end()) {
                logger::error("Actor {} is not part of a scene assignment.", a_actor->GetFormID());
                return 0;
            }
            uniquePositions.insert(std::distance(assignment.begin(), actorIt));
        }

        const auto currentIt = uniquePositions.find(currentPosition);
        return currentIt == uniquePositions.end() ? 0 : static_cast<int32_t>(std::distance(uniquePositions.begin(), currentIt) + 1);
    }

    bool Instance::SetNextPermutation(RE::Actor* a_actor)
    {
        const auto position = GetPosition(a_actor);
        if (!position) {
            logger::error("Actor {} is not part of the current scene.", a_actor->GetFormID());
            return false;
        }
        if (position->uniquePermutations < 2) {
            logger::info("Actor {} has no alternative permutations.", a_actor->GetFormID());
            return false;
        }

        std::set<ptrdiff_t> uniquePositions;
        for (const auto& assignment : assignments) {
            const auto actorIt = std::find(assignment.begin(), assignment.end(), a_actor);
            if (actorIt == assignment.end()) {
                logger::error("Actor {} is not part of a scene assignment.", a_actor->GetFormID());
                return false;
            }
            uniquePositions.insert(std::distance(assignment.begin(), actorIt));
        }

        const auto currentActorIt = std::find(activeAssignment->begin(), activeAssignment->end(), a_actor);
        if (currentActorIt == activeAssignment->end()) {
            logger::error("Actor {} is not part of the current assignment.", a_actor->GetFormID());
            return false;
        }
        const auto currentPosition = std::distance(activeAssignment->begin(), currentActorIt);
        auto targetPosition = uniquePositions.upper_bound(currentPosition);
        if (targetPosition == uniquePositions.end())
            targetPosition = uniquePositions.begin();

        for (auto it = assignments.begin(); it < assignments.end(); it++) {
            const auto actorIt = std::find(it->begin(), it->end(), a_actor);
            if (std::distance(it->begin(), actorIt) == *targetPosition) {
                activeAssignment = it;
                UnregisterNiInstance();
                UnregisterNiInstanceLegacy();
                AdvanceScene(activeStage);
                logger::info("Actor {} changed to scene position {}.", a_actor->GetFormID(), *targetPosition + 1);
                return true;
            }
        }
        logger::warn("Actor {} has no alternative permutations.", a_actor->GetFormID());
        return false;
    }

    // ── CONFIGS STATE COMMUNICATION

    template <typename T>
    T Instance::GetThreadProperty(const std::string& a_property)
    {
        const auto scriptObj = Script::GetScriptObject(linkedQst, "sslThreadModel");
        if (!scriptObj)
            return T{};
        return Script::GetTrivialProperty<T>(scriptObj, a_property);
    }
    template bool Instance::GetThreadProperty<bool>(const std::string&);
    template float Instance::GetThreadProperty<float>(const std::string&);
    template int32_t Instance::GetThreadProperty<int32_t>(const std::string&);

    template <typename T>
    void Instance::SetThreadProperty(const std::string& a_property, T a_val)
    {
        const auto scriptObj = Script::GetScriptObject(linkedQst, "sslThreadModel");
        if (!scriptObj)
            return;
        Script::SetProperty<T>(scriptObj, a_property, a_val);
    }
    template void Instance::SetThreadProperty<bool>(const std::string&, bool);
    template void Instance::SetThreadProperty<float>(const std::string&, float);
    template void Instance::SetThreadProperty<int32_t>(const std::string&, int32_t);

    // ── SCENE HUD

    void Instance::InitSceneHUDImpl()
    {
        auto& sceneHUD = Interface::SceneHUD::GetSingleton();
        if (!sceneHUD.IsActive() || sceneHUD.GetForThread(linkedQst))
            sceneHUD.Init(linkedQst);
    }

    void Instance::DestroySceneHUDImpl()
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->Destroy();
    }

    void Instance::SetFocusSceneHUDImpl(bool a_focused)
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->SetFocus(a_focused);
    }

    void Instance::UpdateMenuTimerDisplay(float a_duration, float a_left)
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->UpdateStageTimer(a_duration, a_left);
    }

    void Instance::EnjBarsChangeHighlightedPartner(RE::Actor* a_partner)
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->UpdateHighlightedPartner(a_partner);
    }

    void Instance::EnjBarsUpdateSlider(RE::Actor* a_position, float a_enjoyment, RE::BSFixedString a_interactions)
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->UpdateEnjoyment(a_position, a_enjoyment, a_interactions);
    }

    void Instance::RegisterRaiseEnjAttempt(RE::Actor* a_position, float a_nextTimeCycle)
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->RegisterRaiseEnjoymentAttempt(a_position, a_nextTimeCycle);
    }

    void Instance::OnStageChangedUpdateHUD()
    {
        if (auto* sceneHUD = Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            sceneHUD->RefreshStageOffsets();
        Interface::StageSelectMenu::GetSingleton().RefreshSceneGraphView(linkedQst);
    }

    bool Instance::OpenStageSelectMenuImpl()
    {
        if (!Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            return false;
        return Interface::StageSelectMenu::GetSingleton().OpenStageSelectMenu(linkedQst);
    }

    void Instance::SetVisibilitySceneGraphImpl(bool a_open)
    {
        if (Interface::SceneHUD::GetSingleton().GetForThread(linkedQst))
            Interface::StageSelectMenu::GetSingleton().SetVisibilitySceneGraph(linkedQst, a_open);
    }

}  // namespace Thread
