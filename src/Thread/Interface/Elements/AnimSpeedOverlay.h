#pragma once
namespace Thread::Interface
{
    class SceneHUD;

    class AnimSpeedOverlay final
    {
      public:
        void Render(SceneHUD& a_hud);
        static void StepSpeed(RE::TESQuest* a_quest, bool a_increase);
        void UpdateStageTimer(float a_duration, float a_timer);

      private:
        static void OnSpeedChange(RE::TESQuest* a_quest, float a_delta);

        float _stageDuration{ 0.0f };
        float _stageTimer{ 0.0f };
    };
}
