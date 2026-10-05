#include "CollisionHandler.h"

namespace Thread::Collision
{
    namespace
    {
        [[nodiscard]] auto GetTESObjectREFR(const RE::hkpCollidable* a_collidable) -> RE::TESObjectREFR*
        {
            if (!a_collidable || a_collidable->ownerOffset >= 0) {
                return nullptr;
            }

            using enum RE::hkpWorldObject::BroadPhaseType;
            switch (static_cast<RE::hkpWorldObject::BroadPhaseType>(a_collidable->broadPhaseHandle.type)) {
            case kEntity:
                if (auto* body = a_collidable->GetOwner<RE::hkpRigidBody>()) {
                    return body->GetUserData();
                }
                break;
            case kPhantom:
                if (auto* phantom = a_collidable->GetOwner<RE::hkpPhantom>()) {
                    return phantom->GetUserData();
                }
                break;
            default:
                break;
            }

            return nullptr;
        }

        [[nodiscard]] auto GetCollisionLayer(const RE::hkpCollidable* a_collidable) -> RE::COL_LAYER
        {
            if (!a_collidable) {
                return RE::COL_LAYER::kUnidentified;
            }
            auto info = *reinterpret_cast<const std::uint32_t*>(&a_collidable->broadPhaseHandle.collisionFilterInfo);
            return static_cast<RE::COL_LAYER>(info & 0x7F);
        }

        [[nodiscard]] constexpr bool IsBipedCollisionLayer(RE::COL_LAYER a_layer) noexcept
        {
            using enum RE::COL_LAYER;
            switch (a_layer) {
            case kBiped:
            case kCharController:
            case kDeadBip:
            case kBipedNoCC:
                return true;
            default:
                return false;
            }
        }

        constexpr void ZeroVector4(RE::hkVector4& a_vec)
        {
            a_vec.quad.m128_f32[0] = 0.0f;
            a_vec.quad.m128_f32[1] = 0.0f;
            a_vec.quad.m128_f32[2] = 0.0f;
            a_vec.quad.m128_f32[3] = 0.0f;
        }

        constexpr void SetUnitZVector4(RE::hkVector4& a_vec)
        {
            a_vec.quad.m128_f32[0] = 0.0f;
            a_vec.quad.m128_f32[1] = 0.0f;
            a_vec.quad.m128_f32[2] = 1.0f;
            a_vec.quad.m128_f32[3] = 0.0f;
        }

        struct hkbFootIkDriver : RE::hkReferencedObject
        {
            std::byte pad10[0x20];
            RE::hkQuaternion alignedGroundRotation;
            std::uint64_t unk40;
            std::uint16_t unk48;
            bool disableFootIk;
            std::byte pad4B[5];
        };
        static_assert(offsetof(hkbFootIkDriver, alignedGroundRotation) == 0x30);
        static_assert(offsetof(hkbFootIkDriver, disableFootIk) == 0x4A);

        struct ShadowhkbCharacter : RE::hkReferencedObject
        {
            std::byte pad10[0x30];
            RE::hkRefPtr<hkbFootIkDriver> footIkDriver;
        };
        static_assert(offsetof(ShadowhkbCharacter, footIkDriver) == 0x40);

        struct FootIKSnapshot
        {
            RE::hkRefPtr<hkbFootIkDriver> driver;
            RE::hkQuaternion rotation;
            bool disabled;
            size_t owners{ 0 };
        };
        struct ActorFootIKState
        {
            RE::BSAnimationGraphManagerPtr manager;
            std::vector<hkbFootIkDriver*> drivers;
        };
        struct ControllerSnapshot
        {
            RE::NiPointer<RE::bhkCharacterController> controller;
            std::array<bool, 4> original;
            size_t owners{ 0 };
        };
        constexpr std::array controllerFlags{
            RE::CHARACTER_FLAGS::kNoGravityOnGround, RE::CHARACTER_FLAGS::kNoSim,
            RE::CHARACTER_FLAGS::kNotPushablePermanent, RE::CHARACTER_FLAGS::kPossiblePathObstacle };
        std::unordered_map<RE::bhkCharacterController*, ControllerSnapshot> controllerSnapshots;
        std::unordered_map<RE::FormID, std::vector<RE::bhkCharacterController*>> actorControllers;
        // Protected by CollisionHandler::_mutex. Graph locks are acquired first.
        std::unordered_map<hkbFootIkDriver*, FootIKSnapshot> footIKSnapshots;
        std::unordered_map<RE::FormID, ActorFootIKState> actorFootIKStates;
    }

    void CollisionHandler::Install()
    {
        auto& trampoline = SKSE::GetTrampoline();

        REL::Relocation<std::uintptr_t> vtbl{ RE::VTABLE_bhkCollisionFilter[1] };
        _IsCollisionEnabled = vtbl.write_vfunc(0x1, IsCollisionEnabled);

        REL::Relocation<std::uintptr_t> target{ RELOCATION_ID(36359, 37350) };
        _originalApplyMovementDelta = trampoline.write_call<5>(target.address() + OFFSET(0xF0, 0xFB), Hook_ApplyMovementDelta);

        logger::info("CollisionHandler hook installed.");
    }

    void CollisionHandler::Clear()
    {
        decltype(_rigidBodyStates) releaseAfterUnlock;
        decltype(controllerSnapshots) releaseControllersAfterUnlock;
        decltype(actorControllers) releaseControllerOwnersAfterUnlock;
        decltype(footIKSnapshots) releaseDriversAfterUnlock;
        decltype(actorFootIKStates) releaseGraphsAfterUnlock;
        const std::unique_lock lock{ _mutex };
        _cache.clear();
        // Revert discards state from the old world; do not write into it.
        releaseAfterUnlock.swap(_rigidBodyStates);
        releaseControllersAfterUnlock.swap(controllerSnapshots);
        releaseControllerOwnersAfterUnlock.swap(actorControllers);
        releaseDriversAfterUnlock.swap(footIKSnapshots);
        releaseGraphsAfterUnlock.swap(actorFootIKStates);
    }

    bool CollisionHandler::HasActor(RE::FormID a_actor)
    {
        const std::shared_lock lock{ _mutex };
        return std::ranges::contains(_cache, a_actor);
    }

    void CollisionHandler::CaptureController(RE::FormID a_actor, RE::bhkCharacterController* a_controller)
    {
        auto& controllers = actorControllers[a_actor];
        if (std::ranges::contains(controllers, a_controller))
            return;
        controllers.reserve(controllers.size() + 1);
        auto [saved, inserted] = controllerSnapshots.try_emplace(a_controller, ControllerSnapshot{
            RE::NiPointer<RE::bhkCharacterController>{ a_controller },
            { a_controller->flags.any(controllerFlags[0]), a_controller->flags.any(controllerFlags[1]),
                a_controller->flags.any(controllerFlags[2]), a_controller->flags.any(controllerFlags[3]) } });
        ++saved->second.owners;
        controllers.push_back(a_controller);
    }

    void CollisionHandler::RestoreControllers(RE::FormID a_actor, std::vector<RE::NiPointer<RE::bhkCharacterController>>& a_releaseAfterUnlock)
    {
        const auto owner = actorControllers.find(a_actor);
        if (owner == actorControllers.end())
            return;
        a_releaseAfterUnlock.reserve(owner->second.size());
        for (auto* controller : owner->second) {
            auto saved = controllerSnapshots.find(controller);
            if (saved == controllerSnapshots.end() || --saved->second.owners != 0)
                continue;
            for (size_t i = 0; i < controllerFlags.size(); ++i) {
                if (saved->second.original[i])
                    controller->flags.set(controllerFlags[i]);
                else
                    controller->flags.reset(controllerFlags[i]);
            }
            a_releaseAfterUnlock.push_back(std::move(saved->second.controller));
            controllerSnapshots.erase(saved);
        }
        actorControllers.erase(owner);
    }

    void CollisionHandler::ConfigureControllerForNoCollision(RE::bhkCharacterController* a_controller)
    {
        a_controller->pitchAngle = 0.0f;
        a_controller->rollAngle = 0.0f;
        a_controller->calculatePitchTimer = 55.0f;

        RE::hkVector4 zeroVec{};
        ZeroVector4(zeroVec);
        a_controller->SetLinearVelocityImpl(zeroVec);

        ZeroVector4(a_controller->outVelocity);
        ZeroVector4(a_controller->initialVelocity);
        ZeroVector4(a_controller->velocityMod);
        ZeroVector4(a_controller->pushDelta);
        ZeroVector4(a_controller->fakeSupportStart);
        SetUnitZVector4(a_controller->supportNorm);

        a_controller->flags.set(
            RE::CHARACTER_FLAGS::kNoGravityOnGround,
            RE::CHARACTER_FLAGS::kNoSim,
            RE::CHARACTER_FLAGS::kSupport);

        a_controller->flags.reset(
            RE::CHARACTER_FLAGS::kCheckSupport,
            RE::CHARACTER_FLAGS::kHasPotentialSupportManifold,
            RE::CHARACTER_FLAGS::kStuckQuad,
            RE::CHARACTER_FLAGS::kOnStairs,
            RE::CHARACTER_FLAGS::kTryStep);

        a_controller->context.currentState = RE::hkpCharacterStateType::kSwimming;
    }

    void CollisionHandler::DisableRigidBodyPhysics(RE::Actor* a_actor)
    {
        auto* process = a_actor->GetMiddleHighProcess();
        if (!process)
            return;

        auto* controller = process->charController.get();
        if (!controller)
            return;

        controller->flags.set(RE::CHARACTER_FLAGS::kNotPushablePermanent);
        controller->flags.reset(RE::CHARACTER_FLAGS::kPossiblePathObstacle);
        ZeroVector4(controller->surfaceInfo.surfaceVelocity);

        auto* rigidBodyController = skyrim_cast<RE::bhkCharRigidBodyController*>(controller);
        if (!rigidBodyController)
            return;

        auto* hkCharRB = *reinterpret_cast<RE::hkpCharacterRigidBody**>(
            reinterpret_cast<std::uintptr_t>(&rigidBodyController->charRigidBody) + 0x10);

        if (hkCharRB && hkCharRB->character && hkCharRB->character->GetCollidableRW()) {
            auto& motion = hkCharRB->character->motion;
            _rigidBodyStates.try_emplace(a_actor->GetFormID(), RigidBodyState{
                RE::hkRefPtr<RE::hkpRigidBody>{ hkCharRB->character },
                motion.inertiaAndMassInv.quad.m128_f32[3], motion.gravityFactor });
            hkCharRB->character->motion.SetMassInv(0.0f);
            hkCharRB->character->motion.gravityFactor = 0.0f;
        }
    }

    void CollisionHandler::RestoreRigidBodyPhysics(RE::Actor* a_actor)
    {
        auto* process = a_actor->GetMiddleHighProcess();
        if (!process)
            return;

        auto* controller = process->charController.get();
        if (!controller)
            return;

        // Persistent control flags are restored from snapshots; transient support
        // and locomotion state retain the existing engine reinitialization path.
        controller->flags.set(
            RE::CHARACTER_FLAGS::kSupport,
            RE::CHARACTER_FLAGS::kCheckSupport);

        controller->context.currentState = RE::hkpCharacterStateType::kOnGround;
    }

    void CollisionHandler::RestoreSavedPhysics(RE::FormID a_actor, RE::hkRefPtr<RE::hkpRigidBody>& a_releaseAfterUnlock)
    {
        const auto saved = _rigidBodyStates.find(a_actor);
        if (saved == _rigidBodyStates.end())
            return;
        auto& motion = saved->second.body->motion;
        motion.SetMassInv(saved->second.massInv);
        motion.gravityFactor = saved->second.gravityFactor;
        // The caller declares this owner before its lock, so final body release
        // cannot invoke engine destruction callbacks while _mutex is held.
        a_releaseAfterUnlock = saved->second.body;
        _rigidBodyStates.erase(saved);
    }

    void CollisionHandler::DisableFootIK(RE::Actor* a_actor)
    {
        if (!a_actor)
            return;
        const auto actorID = a_actor->GetFormID();
        RE::BSAnimationGraphManagerPtr graphMgr;
        if (!a_actor->GetAnimationGraphManager(graphMgr) || !graphMgr)
            return;

        RE::BSSpinLockGuard graphLock(graphMgr->GetRuntimeData().updateLock);
        const std::unique_lock cacheLock{ _mutex };
        // A removal may have completed while we waited for the graph lock.
        if (!std::ranges::contains(_cache, actorID) || actorFootIKStates.contains(actorID))
            return;
        ActorFootIKState pendingState{ graphMgr, {} };
        pendingState.drivers.reserve(graphMgr->graphs.size());
        footIKSnapshots.reserve(footIKSnapshots.size() + graphMgr->graphs.size());
        auto owner = actorFootIKStates.emplace(actorID, std::move(pendingState)).first;
        auto& state = owner->second;
        for (auto& graph : graphMgr->graphs) {
            if (!graph)
                continue;
            auto* shadow = reinterpret_cast<ShadowhkbCharacter*>(&graph->characterInstance);
            auto* driver = shadow->footIkDriver.get();
            if (!driver || std::ranges::contains(state.drivers, driver))
                continue;
            auto saved = footIKSnapshots.try_emplace(driver, FootIKSnapshot{
                RE::hkRefPtr<hkbFootIkDriver>{ driver }, driver->alignedGroundRotation, driver->disableFootIk }).first;
            state.drivers.push_back(driver);
            ++saved->second.owners;
            driver->disableFootIk = true;
            driver->alignedGroundRotation.vec = { 0.0f, 0.0f, 0.0f, 1.0f };
        }
    }

    void CollisionHandler::RestoreFootIK(RE::FormID a_actor)
    {
        // Retain owners before acquiring locks; their final release stays outside locks.
        std::vector<FootIKSnapshot> releaseDriversAfterUnlock;
        RE::BSAnimationGraphManagerPtr manager;
        {
            const std::shared_lock cacheLock{ _mutex };
            const auto state = actorFootIKStates.find(a_actor);
            if (state == actorFootIKStates.end())
                return;
            manager = state->second.manager;
        }
        RE::BSSpinLockGuard graphLock(manager->GetRuntimeData().updateLock);
        const std::unique_lock cacheLock{ _mutex };
        const auto state = actorFootIKStates.find(a_actor);
        // Revert or a new registration may have changed ownership while waiting.
        if (state == actorFootIKStates.end() || state->second.manager != manager || std::ranges::contains(_cache, a_actor))
            return;
        releaseDriversAfterUnlock.reserve(state->second.drivers.size());
        for (auto* driver : state->second.drivers) {
            const auto saved = footIKSnapshots.find(driver);
            if (saved == footIKSnapshots.end() || --saved->second.owners != 0)
                continue;
            driver->disableFootIk = saved->second.disabled;
            driver->alignedGroundRotation = saved->second.rotation;
            releaseDriversAfterUnlock.push_back(std::move(saved->second));
            footIKSnapshots.erase(saved);
        }
        actorFootIKStates.erase(state);
    }

    void CollisionHandler::Hook_ApplyMovementDelta(RE::Actor* a_actor, float a_delta)
    {
        if (a_actor) {
            std::unique_lock lock{ _mutex };
            if (std::ranges::contains(_cache, a_actor->GetFormID())) {
                if (auto* process = a_actor->GetMiddleHighProcess()) {
                    if (auto* controller = process->charController.get()) {
                        CaptureController(a_actor->GetFormID(), controller);
                        ConfigureControllerForNoCollision(controller);
                        return;
                    }
                }
            }
        }
        _originalApplyMovementDelta(a_actor, a_delta);
    }

    bool* CollisionHandler::IsCollisionEnabled(RE::hkpCollidableCollidableFilter* a_this, bool* a_result, const RE::hkpCollidable* a_collidableA, const RE::hkpCollidable* a_collidableB)
    {
        a_result = _IsCollisionEnabled(a_this, a_result, a_collidableA, a_collidableB);

        if (!*a_result) {
            return a_result;
        }

        if (!IsBipedCollisionLayer(GetCollisionLayer(a_collidableA)) ||
            !IsBipedCollisionLayer(GetCollisionLayer(a_collidableB))) {
            return a_result;
        }

        auto* refA = GetTESObjectREFR(a_collidableA);
        auto* refB = GetTESObjectREFR(a_collidableB);

        if (!refA || !refB || refA == refB) {
            return a_result;
        }

        auto* actorA = refA->As<RE::Actor>();
        auto* actorB = refB->As<RE::Actor>();

        if (actorA && actorB) {
            auto idA = actorA->GetFormID();
            auto idB = actorB->GetFormID();
            const std::shared_lock lock{ _mutex };
            if (std::ranges::any_of(_cache, [=](RE::FormID id) { return id == idA || id == idB; })) {
                *a_result = false;
            }
        }

        return a_result;
    }

    void CollisionHandler::AddActor(RE::FormID a_actor)
    {
        auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_actor);
        {
            const std::unique_lock lock{ _mutex };
            if (std::ranges::contains(_cache, a_actor))
                return;
            _cache.push_back(a_actor);
            if (!actor)
                return;
            if (auto* process = actor->GetMiddleHighProcess()) {
                if (auto* controller = process->charController.get()) {
                    CaptureController(a_actor, controller);
                    ConfigureControllerForNoCollision(controller);
                }
            }
            DisableRigidBodyPhysics(actor);
        }
        // Never wait for a graph update lock while holding the collision cache lock.
        DisableFootIK(actor);
    }

    void CollisionHandler::RemoveActor(RE::FormID a_actor)
    {
        RE::hkRefPtr<RE::hkpRigidBody> releaseAfterUnlock;
        std::vector<RE::NiPointer<RE::bhkCharacterController>> releaseControllersAfterUnlock;
        {
            const std::unique_lock lock{ _mutex };
            if (std::erase(_cache, a_actor) == 0)
                return;
            RestoreSavedPhysics(a_actor, releaseAfterUnlock);
            if (auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_actor))
                RestoreRigidBodyPhysics(actor);
            RestoreControllers(a_actor, releaseControllersAfterUnlock);
        }
        // Restore the captured graph even if Actor lookup is no longer available.
        RestoreFootIK(a_actor);
    }
}
