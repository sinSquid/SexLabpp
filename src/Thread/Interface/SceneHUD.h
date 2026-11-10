#pragma once

#include "Thread/Interface/UI/Scale.h"
#include "Thread/Interface/UI/Theme.h"
#include "Thread/Interface/UI/Window.h"
#include "Thread/Thread.h"
#include "Util/Script.h"

#include <memory>

namespace Thread::Interface
{
    enum class PanelId : std::uint8_t
    {
        kNone,
        kThreadConfig,
        kSceneSelect,
        kOffsetAdjust,
        kElementControl,
    };

    class SceneHUD final : public RE::BSTEventSink<RE::InputEvent*>
    {
      public:
        // Tasklet updates and render/input callbacks serialize through Instance::LockState().
        static SceneHUD& GetSingleton();

        bool Register();
        void Init(RE::TESQuest* a_quest, bool a_bindSpeedControl = true);
        void Destroy();
        void SetSpeedControl(RE::TESQuest* a_quest, bool a_enabled);

        void SetFocus(bool a_focused);
        void OpenPanel(PanelId a_panel);
        bool PrepareSceneSelect(RE::TESQuest* a_quest);
        bool OpenSceneSelect(RE::TESQuest* a_quest);
        bool OpenExternalSceneSelect(RE::TESQuest* a_quest);
        bool IsExternalSceneSelectCurrent(RE::TESQuest* a_quest, int a_ticket) const;
        bool CloseExternalSceneSelect(RE::TESQuest* a_quest, int a_ticket = -1);
        bool IsExternalSceneSelect() const { const auto stateLock = Instance::LockState(); return _externalSceneSelect; }
        void RequestExternalSceneSelectClose() { const auto stateLock = Instance::LockState(); if (_externalSceneSelect) _externalCloseRequested = true; }
        int GetExternalSceneSelectTicket() const { const auto stateLock = Instance::LockState(); return static_cast<int>(_externalSelectionSerial & 0x7FFFFFFFu); }
        void CloseAllPanels();
        void SetRenderEnabled(bool a_enabled) { const auto stateLock = Instance::LockState(); _renderEnabled = a_enabled; }

        void UpdateStageTimer(float a_duration, float a_timer);
        void UpdateHighlightedPartner(RE::Actor* a_partner);
        void UpdateEnjoyment(RE::Actor* a_actor, float a_enjoyment, RE::BSFixedString a_interactions);
        void RegisterRaiseEnjoymentAttempt(RE::Actor* a_actor, float a_nextTimeCycle);
        void RefreshStageOffsets();
        void RebuildSceneList();

        // Debug node overlay. Collision code feeds shapes through these only; the element itself is private to the HUD.
        [[nodiscard]] bool IsDebugNodeDrawEnabled() const;
        void DebugNodeDrawBeginFrame();
        void DebugNodeDrawPublish();
        void DebugNodeDrawAddRing(const RE::NiPoint3& a_center, const RE::NiPoint3& a_right, const RE::NiPoint3& a_up, float a_radius);
        void DebugNodeDrawAddTaperedCapsule(const RE::NiPoint3& a_start, const RE::NiPoint3& a_end, float a_startRadius, float a_endRadius);

        [[nodiscard]] bool IsActive() const { const auto stateLock = Instance::LockState(); return _linkedThread != nullptr; }
        [[nodiscard]] bool ShouldRender() const { const auto stateLock = Instance::LockState(); return IsActive() && !RE::UI::GetSingleton()->GameIsPaused() && _renderEnabled; }
        [[nodiscard]] bool IsFocused() const { const auto stateLock = Instance::LockState(); return _focused; }
        [[nodiscard]] bool IsPanelOpen(PanelId a_panel) const { const auto stateLock = Instance::LockState(); return _activePanel == a_panel; }
        [[nodiscard]] RE::TESQuest* GetLinkedThread() const { const auto stateLock = Instance::LockState(); return _linkedThread; }
        [[nodiscard]] SceneHUD* GetForThread(RE::TESQuest* a_quest) { const auto stateLock = Instance::LockState(); return a_quest && _linkedThread == a_quest ? this : nullptr; }
        [[nodiscard]] Instance::Access GetThreadInstance() const { const auto stateLock = Instance::LockState(); return Instance::GetInstance(_linkedThread); }
        [[nodiscard]] Script::ObjectPtr GetThreadScript() const { const auto stateLock = Instance::LockState(); return _threadScript; }
        [[nodiscard]] Script::CallbackPtr GetCallback() const { const auto stateLock = Instance::LockState(); return _callback; }
        [[nodiscard]] UI::Scale& GetScale() { return _scale; }

      private:
        struct Elements;

        SceneHUD() = default;
        ~SceneHUD();

        static void __stdcall RenderCallback();
        RE::BSEventNotifyControl ProcessEvent(RE::InputEvent* const* a_event,
            RE::BSTEventSource<RE::InputEvent*>* a_eventSource) override;
        [[nodiscard]] bool CanAdjustSpeed() const;
        [[nodiscard]] bool IsSceneSelectKey(std::uint32_t a_key, RE::InputEvent* a_events) const;
        void Render();

        RE::TESQuest* _linkedThread{};
        Script::ObjectPtr _threadScript{};
        Script::CallbackPtr _callback{};
        UI::Scale _scale;
        UI::FrameworkWindow _window;
        std::unique_ptr<Elements> _elements;
        PanelId _activePanel{ PanelId::kNone };
        bool _registered{ false };
        bool _inputRegistered{ false };
        RE::TESQuest* _speedThread{};
        std::uint64_t _controlGeneration{ 0 };
        bool _focused{ false };
        bool _externalSceneSelect{ false };
        bool _externalCloseRequested{ false };
        std::uint32_t _externalSelectionSerial{ 0 };
        bool _renderEnabled{ true };
    };
}
