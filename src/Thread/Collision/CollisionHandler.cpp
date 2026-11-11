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

        constexpr std::uint32_t kOwnedControllerFlags =
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kNoGravityOnGround) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kNoSim) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kSupport) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kCheckSupport) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kHasPotentialSupportManifold) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kStuckQuad) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kOnStairs) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kTryStep) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kNotPushablePermanent) |
            static_cast<std::uint32_t>(RE::CHARACTER_FLAGS::kPossiblePathObstacle);

        struct FootIKState
        {
            RE::hkRefPtr<RE::hkbFootIkDriver> driver;
            std::uint8_t disabled;
            RE::hkQuaternion alignedGroundRotation;
        };

        struct PhysicsState
        {
            RE::NiPointer<RE::bhkCharacterController> controller;
            RE::hkRefPtr<RE::hkpRigidBody> rigidBody;
            std::uint32_t flags{ 0 };
            RE::hkpCharacterStateType characterState{ RE::hkpCharacterStateType::kOnGround };
            float pitchAngle{ 0.0f };
            float rollAngle{ 0.0f };
            float calculatePitchTimer{ 0.0f };
            float massInverse{ 0.0f };
            RE::hkHalf gravityFactor;
            std::vector<FootIKState> footIK;
        };

        // Guarded by CollisionHandler::_mutex together with its actor cache.
        // Strong identity references prevent a recycled address from matching a
        // replacement controller/body/driver during restoration.
        std::unordered_map<RE::FormID, PhysicsState> physicsStates;

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
        const std::unique_lock lock{ _mutex };
        for (const auto id : _cache) {
            if (auto* actor = RE::TESForm::LookupByID<RE::Actor>(id)) {
                SetFootIKEnabled(actor, true);
                RestoreRigidBodyPhysics(actor);
            }
        }
        _cache.clear();
        physicsStates.clear();
    }

    bool CollisionHandler::HasActor(RE::FormID a_actor)
    {
        const std::shared_lock lock{ _mutex };
        return std::ranges::contains(_cache, a_actor);
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
        auto* controller = process ? process->charController.get() : nullptr;
        if (!controller)
            return;

        auto& state = physicsStates.try_emplace(a_actor->GetFormID()).first->second;
        if (state.controller.get() != controller) {
            state.controller = controller;
            state.flags = controller->flags.underlying();
            state.characterState = controller->context.currentState;
            state.pitchAngle = controller->pitchAngle;
            state.rollAngle = controller->rollAngle;
            state.calculatePitchTimer = controller->calculatePitchTimer;
            state.rigidBody.reset();
        }
        auto* body = controller->GetRigidBody();
        if (body && state.rigidBody.get() != body) {
            state.rigidBody = RE::hkRefPtr<RE::hkpRigidBody>{ body };
            state.massInverse = body->motion.inertiaAndMassInv.quad.m128_f32[3];
            state.gravityFactor = body->motion.gravityFactor;
        }

        controller->flags.set(RE::CHARACTER_FLAGS::kNotPushablePermanent);
        controller->flags.reset(RE::CHARACTER_FLAGS::kPossiblePathObstacle);
        ZeroVector4(controller->surfaceInfo.surfaceVelocity);
        if (body) {
            body->motion.SetMassInv(0.0f);
            body->motion.gravityFactor = 0.0f;
        }
    }

    void CollisionHandler::RestoreRigidBodyPhysics(RE::Actor* a_actor)
    {
        const auto where = physicsStates.find(a_actor->GetFormID());
        if (where == physicsStates.end())
            return;
        const auto& state = where->second;
        auto* process = a_actor->GetMiddleHighProcess();
        auto* controller = process ? process->charController.get() : nullptr;
        if (!controller || state.controller.get() != controller)
            return;

        // Only undo bits owned by this module; other flags may have changed.
        controller->flags = static_cast<RE::CHARACTER_FLAGS>(
            (controller->flags.underlying() & ~kOwnedControllerFlags) | (state.flags & kOwnedControllerFlags));
        if (controller->context.currentState == RE::hkpCharacterStateType::kSwimming)
            controller->context.currentState = state.characterState;
        if (controller->pitchAngle == 0.0f)
            controller->pitchAngle = state.pitchAngle;
        if (controller->rollAngle == 0.0f)
            controller->rollAngle = state.rollAngle;
        if (controller->calculatePitchTimer == 55.0f)
            controller->calculatePitchTimer = state.calculatePitchTimer;

        auto* body = controller->GetRigidBody();
        if (body && state.rigidBody.get() == body) {
            if (body->motion.inertiaAndMassInv.quad.m128_f32[3] == 0.0f)
                body->motion.SetMassInv(state.massInverse);
            if (static_cast<float>(body->motion.gravityFactor) == 0.0f)
                body->motion.gravityFactor = state.gravityFactor;
        }
    }

    void CollisionHandler::SetFootIKEnabled(RE::Actor* a_actor, bool a_enabled)
    {
        if (!a_actor)
            return;
        const auto where = physicsStates.find(a_actor->GetFormID());
        if (where == physicsStates.end())
            return;
        auto& state = where->second;

        RE::BSAnimationGraphManagerPtr graphMgr;
        if (!a_actor->GetAnimationGraphManager(graphMgr) || !graphMgr)
            return;

        RE::BSSpinLockGuard locker(graphMgr->GetRuntimeData().updateLock);
        for (auto& graph : graphMgr->graphs) {
            if (!graph)
                continue;
            auto* driver = graph->characterInstance.footIkDriver.get();
            if (!driver)
                continue;
            const auto saved = std::ranges::find_if(state.footIK, [&](const FootIKState& saved) {
                return saved.driver.get() == driver;
            });
            if (a_enabled) {
                if (saved != state.footIK.end()) {
                    driver->disableFootIk = saved->disabled;
                    driver->alignWithGroundRotation = saved->alignedGroundRotation;
                }
            } else {
                if (saved == state.footIK.end()) {
                    state.footIK.push_back({ RE::hkRefPtr<RE::hkbFootIkDriver>{ driver }, driver->disableFootIk, driver->alignWithGroundRotation });
                }
                driver->disableFootIk = 1;
                driver->alignWithGroundRotation.vec = { 0.0f, 0.0f, 0.0f, 1.0f };
            }
        }
    }

    void CollisionHandler::Hook_ApplyMovementDelta(RE::Actor* a_actor, float a_delta)
    {
        if (a_actor) {
            std::unique_lock lock{ _mutex };
            if (std::ranges::contains(_cache, a_actor->GetFormID())) {
                if (auto* process = a_actor->GetMiddleHighProcess()) {
                    if (auto* controller = process->charController.get()) {
                        // A replacement controller needs its own pristine snapshot.
                        DisableRigidBodyPhysics(a_actor);
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
        const std::unique_lock lock{ _mutex };

        if (std::ranges::contains(_cache, a_actor))
            return;

        _cache.push_back(a_actor);
        physicsStates.try_emplace(a_actor);

        auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_actor);
        if (!actor)
            return;

        DisableRigidBodyPhysics(actor);
        if (auto* process = actor->GetMiddleHighProcess()) {
            if (auto* controller = process->charController.get()) {
                ConfigureControllerForNoCollision(controller);
            }
        }

        SetFootIKEnabled(actor, false);
    }

    void CollisionHandler::RemoveActor(RE::FormID a_actor)
    {
        const std::unique_lock lock{ _mutex };
        if (std::erase(_cache, a_actor) == 0) {
            return;
        }

        auto* actor = RE::TESForm::LookupByID<RE::Actor>(a_actor);
        if (actor) {
            SetFootIKEnabled(actor, true);
            RestoreRigidBodyPhysics(actor);
        }
        physicsStates.erase(a_actor);
    }
}
