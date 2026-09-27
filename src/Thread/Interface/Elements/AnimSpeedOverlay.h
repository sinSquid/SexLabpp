#pragma once
namespace Thread::Interface
{
    class SceneHUD;

    class AnimSpeedOverlay final
    {
      public:
        void Render(SceneHUD& a_hud);
        void StepSpeed(SceneHUD& a_hud, bool a_increase);
        void UpdateStageTimer(float a_duration, float a_timer);

      private:
        void OnSpeedChange(SceneHUD& a_hud, float a_delta);

        float _stageDuration{ 0.0f };
        float _stageTimer{ 0.0f };
    };
}
