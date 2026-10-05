#pragma once

#include <array>
#include <shared_mutex>
#include <unordered_map>
#include <vector>

namespace Thread::Collision
{
    class CollisionHandler final : public Singleton<CollisionHandler>
    {
      public:
        static void Install();
        static void AddActor(RE::FormID a_actor);
        static void RemoveActor(RE::FormID a_actor);
        static void Clear();

        [[nodiscard]] static bool HasActor(RE::FormID a_actor);

      private:
        static void CaptureController(RE::FormID a_actor, RE::bhkCharacterController* a_controller);
        static void RestoreControllers(RE::FormID a_actor, std::vector<RE::NiPointer<RE::bhkCharacterController>>& a_releaseAfterUnlock);
        static void ConfigureControllerForNoCollision(RE::bhkCharacterController* a_controller);
        static void DisableRigidBodyPhysics(RE::Actor* a_actor);
        static void RestoreRigidBodyPhysics(RE::Actor* a_actor);
        static void RestoreSavedPhysics(RE::FormID a_actor, RE::hkRefPtr<RE::hkpRigidBody>& a_releaseAfterUnlock);
        static void DisableFootIK(RE::Actor* a_actor);
        static void RestoreFootIK(RE::FormID a_actor);

        static bool* IsCollisionEnabled(
            RE::hkpCollidableCollidableFilter* a_this,
            bool* a_result,
            const RE::hkpCollidable* a_collidableA,
            const RE::hkpCollidable* a_collidableB);

        static void Hook_ApplyMovementDelta(RE::Actor* a_actor, float a_delta);

        static inline REL::Relocation<decltype(IsCollisionEnabled)> _IsCollisionEnabled;
        static inline REL::Relocation<decltype(Hook_ApplyMovementDelta)> _originalApplyMovementDelta;

        static inline std::vector<RE::FormID> _cache;
        struct RigidBodyState
        {
            RE::hkRefPtr<RE::hkpRigidBody> body;
            float massInv;
            RE::hkHalf gravityFactor;
        };
        // Accessed under _mutex. Hold the captured body alive until removal/revert.
        static inline std::unordered_map<RE::FormID, RigidBodyState> _rigidBodyStates;
        static inline std::shared_mutex _mutex;
    };
}
