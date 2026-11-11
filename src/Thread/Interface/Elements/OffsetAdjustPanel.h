#pragma once

#include "Thread/Interface/SceneHUD.h"

namespace Thread::Interface
{
    class OffsetAdjustPanel final
    {
      public:
        void Open(SceneHUD& a_hud);
        void Close();
        void Render(SceneHUD& a_hud);
        void RefreshStageOffsets(SceneHUD& a_hud);

      private:
        struct AxisState
        {
            float value{};
            float baseline{};
            float dragStartValue{};
            bool hasBaseline{ false };
        };

        struct AxisDefinition
        {
            const char* label;
            Registry::CoordinateType coordinate;
            float displayRange;
        };

        static constexpr float kTranslationDisplayRange = 200.0f;
        static constexpr float kRotationDisplayRange = 180.0f;
        static constexpr std::array kAxisDefinitions{
            AxisDefinition{ "X", Registry::CoordinateType::X, kTranslationDisplayRange },
            AxisDefinition{ "Y", Registry::CoordinateType::Y, kTranslationDisplayRange },
            AxisDefinition{ "Z", Registry::CoordinateType::Z, kTranslationDisplayRange },
            AxisDefinition{ "R", Registry::CoordinateType::R, kRotationDisplayRange },
        };

        struct TargetItem
        {
            RE::Actor* actor{};
            std::uint32_t formId{};
            std::size_t positionIndex{};
            const Registry::Scene* sourceScene{};
            const Registry::Stage* sourceStage{};
            std::uint32_t mappingRevision{};
            std::string label;
            std::array<AxisState, kAxisDefinitions.size()> axes{};
            std::optional<std::size_t> draggingAxis;
            bool isCenter{ false };
            bool valid{ true };
            bool open{ true };
        };

        void OnSetOffset(SceneHUD& a_hud, Registry::CoordinateType a_axis, std::uint32_t a_targetId, float a_value);
        void OnResetOffsets(SceneHUD& a_hud);
        void OnSetAdjustStageOnly(SceneHUD& a_hud, bool a_state);

        void RefreshTargets(SceneHUD& a_hud);
        void RefreshValues(SceneHUD& a_hud, TargetItem& a_target);
        void RenderTargetCard(SceneHUD& a_hud, TargetItem& a_target, std::size_t a_targetIndex);
        bool OffsetTrack(UI::Scale& a_scale, const AxisDefinition& a_axis, AxisState& a_state, float a_width, bool& a_draggingOut);

        std::vector<TargetItem> _targets;
        bool _hasFurnitureCenter{ false };
        bool _adjustStageOnly{ false };
    };
}
