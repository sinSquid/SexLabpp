#include "SceneHUD.h"
#include "Elements/AnimSpeedOverlay.h"
#include "Elements/ElementCtrlPanel.h"
#include "Elements/EnjBarsOverlay.h"
#include "Elements/OffsetAdjustPanel.h"
#include "Elements/PseudoPanelStack.h"
#include "Elements/SceneSelectPanel.h"
#include "Elements/ThreadConfigPanel.h"
#include "Elements/DebugNodeDraw.h"

namespace Thread::Interface
{
    struct SceneHUD::Elements
    {
        AnimSpeedOverlay animSpeedOverlay;
        EnjBarsOverlay enjoymentBarsOverlay;
        ThreadConfigPanel threadConfigPanel;
        SceneSelectPanel sceneSelectPanel;
        OffsetAdjustPanel offsetAdjustPanel;
        ElementCtrlPanel elementCtrlPanel;
        PseudoPanelStack pseudoPanelStack;
        DebugNodeDraw debugNodeDraw;
    };

    SceneHUD& SceneHUD::GetSingleton()
    {
        static SceneHUD singleton;
        return singleton;
    }

    SceneHUD::~SceneHUD() = default;

    bool SceneHUD::Register()
    {
        if (_registered)
            return true;
        if (!SKSEMenuFramework::IsInstalled()) {
            logger::warn("SceneHUD::Register >> SKSE Menu Framework not installed");
            return false;
        }
        if (!_window.Register(RenderCallback, false)) {
            logger::error("SceneHUD::Register >> AddWindow failed");
            return false;
        }

        _registered = true;
        logger::info("SceneHUD::Register >> UI window registered");
        return true;
    }

    void SceneHUD::Init(RE::TESQuest* a_quest, bool a_bindSpeedControl)
    {
        if (!a_quest)
            return;
        if (!_registered) {
            logger::warn("SceneHUD::Init >> UI window is not registered");
            return;
        }
        if (IsActive())
            Destroy();

        _externalSceneSelect = !a_bindSpeedControl;
        _externalCloseRequested = false;
        ++_externalSelectionSerial;
        _linkedThread = a_quest;
        _threadScript = Script::GetScriptObject(_linkedThread, "sslThreadController");
        auto* instance = GetThreadInstance();
        if (!instance) {
            logger::warn("SceneHUD::Init >> thread instance is null");
            _linkedThread = nullptr;
            _threadScript = nullptr;
            return;
        }

        if (a_bindSpeedControl)
            SetSpeedControl(a_quest, true);
        float scaleMultiplier = a_bindSpeedControl ? instance->GetThreadProperty<float>("VarUI_MenuScaleMult") : Settings::fMenuScaleMult;
        if (scaleMultiplier <= 0.0f) {
            scaleMultiplier = 1.0f;
            instance->SetThreadProperty<float>("VarUI_MenuScaleMult", scaleMultiplier);
        }
        _scale.SetMultiplier(scaleMultiplier);

        float textScaleMultiplier = a_bindSpeedControl ? instance->GetThreadProperty<float>("VarUI_TextScaleMult") : Settings::fMenuTextScaleMult;
        if (textScaleMultiplier <= 0.0f) {
            textScaleMultiplier = 1.0f;
            instance->SetThreadProperty<float>("VarUI_TextScaleMult", textScaleMultiplier);
        }
        _scale.SetTextMultiplier(textScaleMultiplier);

        _activePanel = PanelId::kNone;
        _focused = false;
        _elements = std::make_unique<Elements>();
        if (a_bindSpeedControl)
            _elements->enjoymentBarsOverlay.Init(*instance);
        _window.SetBlocksInput(false);
        _window.Open();
        logger::info("SceneHUD::Init >> scene UI active");
    }

    void SceneHUD::Destroy()
    {
        if (!IsActive() && !_elements && !_externalSceneSelect)
            return;

        _window.SetBlocksInput(false);
        _window.Close();
        _elements.reset();
        _activePanel = PanelId::kNone;
        _focused = false;
        _externalSceneSelect = false;
        _externalCloseRequested = false;
        ++_externalSelectionSerial;
        _linkedThread = nullptr;
        _threadScript = nullptr;
        logger::info("SceneHUD::Destroy >> scene UI deactivated");
    }

    void __stdcall SceneHUD::RenderCallback()
    {
        GetSingleton().Render();
    }

    void SceneHUD::SetSpeedControl(RE::TESQuest* a_quest, bool a_enabled)
    {
        if (!a_quest)
            return;
        if (!a_enabled) {
            if (_speedThread == a_quest) {
                _speedThread = nullptr;
                ++_controlGeneration;
            }
            return;
        }
        if (!Instance::GetInstance(a_quest))
            return;
        if (_speedThread != a_quest) {
            _speedThread = a_quest;
            ++_controlGeneration;
        }
        if (!_inputRegistered) {
            if (auto* input = RE::BSInputDeviceManager::GetSingleton()) {
                input->AddEventSink(this);
                _inputRegistered = true;
            }
        }
    }

    bool SceneHUD::CanAdjustSpeed() const
    {
        return _speedThread && Instance::GetInstance(_speedThread) &&
            !RE::UI::GetSingleton()->GameIsPaused() &&
            (!IsActive() || !_focused || _activePanel == PanelId::kNone);
    }

    bool SceneHUD::IsSceneSelectKey(std::uint32_t a_key, RE::InputEvent* a_events) const
    {
        const auto mainKey = Settings::iOpenSceneSelect;
        const auto modifier = Settings::iSceneSelectModifier;
        if (mainKey < 0 || modifier < 0 || mainKey == modifier)
            return false;
        if (a_key == static_cast<std::uint32_t>(modifier))
            return true;
        if (a_key != static_cast<std::uint32_t>(mainKey))
            return false;
        const auto modifierKey = static_cast<std::uint32_t>(modifier);
        // A fresh modifier has heldDownSecs == 0, so prefer this poll's events.
        std::optional<bool> pressed;
        for (auto* event = a_events; event; event = event->next) {
            auto* button = event->AsButtonEvent();
            if (!button)
                continue;
            const auto code = button->GetIDCode();
            if ((event->GetDevice() == RE::INPUT_DEVICE::kKeyboard && modifierKey < 256 && code == modifierKey) ||
                (event->GetDevice() == RE::INPUT_DEVICE::kMouse && modifierKey >= 256 && modifierKey < 266 && code == modifierKey - 256) ||
                (event->GetDevice() == RE::INPUT_DEVICE::kGamepad && modifierKey >= 266 && code == SKSE::InputMap::GamepadKeycodeToMask(modifierKey)))
                pressed = button->IsPressed();
        }
        if (pressed.has_value())
            return *pressed;
        auto* input = RE::BSInputDeviceManager::GetSingleton();
        if (!input)
            return false;
        if (modifierKey < SKSE::InputMap::kMacro_MouseButtonOffset) {
            const auto* device = input->GetKeyboard();
            // Match BSWin32KeyboardDevice::IsPressed without linking its constructor/vtable object file.
            return device && (device->GetRuntimeData().curState[modifierKey] & 0x80) != 0;
        }
        if (modifierKey < SKSE::InputMap::kMacro_GamepadOffset) {
            const auto* device = input->GetMouse();
            return device && device->IsPressed(modifierKey - SKSE::InputMap::kMacro_MouseButtonOffset);
        }
        const auto* device = input->GetGamepad();
        return device && device->IsPressed(SKSE::InputMap::GamepadKeycodeToMask(modifierKey));
    }

    RE::BSEventNotifyControl SceneHUD::ProcessEvent(RE::InputEvent* const* a_event,
        RE::BSTEventSource<RE::InputEvent*>*)
    {
        if (!a_event || !CanAdjustSpeed())
            return RE::BSEventNotifyControl::kContinue;
        constexpr std::uint32_t kLeftArrow = 203;
        constexpr std::uint32_t kRightArrow = 205;
        for (auto* event = *a_event; event; event = event->next) {
            if (event->GetDevice() != RE::INPUT_DEVICE::kKeyboard)
                continue;
            auto* button = event->AsButtonEvent();
            if (!button || !button->IsDown())
                continue;
            const auto key = button->GetIDCode();
            if (key != kLeftArrow && key != kRightArrow)
                continue;
            if (IsSceneSelectKey(key, *a_event))
                continue;
            const bool increase = key == kRightArrow;
            auto* linkedThread = _speedThread;
            const auto controlGeneration = _controlGeneration;
            SKSE::GetTaskInterface()->AddTask([increase, linkedThread, controlGeneration]() {
                auto& hud = SceneHUD::GetSingleton();
                if (hud._controlGeneration == controlGeneration && hud._speedThread == linkedThread &&
                    hud.CanAdjustSpeed()) {
                    AnimSpeedOverlay::StepSpeed(linkedThread, increase);
                }
            });
        }
        return RE::BSEventNotifyControl::kContinue;
    }

    void SceneHUD::Render()
    {
        if (_externalSceneSelect && !IsExternalSceneSelectCurrent(_linkedThread, GetExternalSceneSelectTicket())) {
            Destroy();
            return;
        }
        if (!_elements || !ShouldRender())
            return;
        auto* instance = GetThreadInstance();
        if (!instance)
            return;

        if (!_externalSceneSelect && instance->GetThreadProperty<bool>("ElementUI_AnimSpeed"))
            _elements->animSpeedOverlay.Render(*this);

        if (!_externalSceneSelect && instance->GetThreadProperty<bool>("ElementUI_EnjBars") &&
            instance->GetThreadProperty<bool>("VarUI_SeparateOrgasm") &&
            instance->GetThreadProperty<bool>("VarUI_HasPlayer")) {
            _elements->enjoymentBarsOverlay.Render(*this);
        }

        if (!_externalSceneSelect && instance->GetThreadProperty<bool>("ElementUI_DebugNodeDraw"))
            _elements->debugNodeDraw.Render(*this);

        if (!_focused)
            return;

        ImGuiMCP::PushStyleVar(ImGuiMCP::ImGuiStyleVar_WindowRounding, _scale.Px(UI::Theme::Geometry.roundingPanel));
        ImGuiMCP::PushStyleVar(ImGuiMCP::ImGuiStyleVar_FrameRounding, _scale.Px(UI::Theme::Geometry.roundingSmall));
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_WindowBg, UI::Theme::Color.panelBackground);
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_Border, UI::Theme::Color.panelBorder);
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_Button, UI::Theme::Color.buttonIdle);
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_ButtonHovered, UI::Theme::Color.buttonHovered);
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_ButtonActive, UI::Theme::Color.buttonPressed);
        _elements->pseudoPanelStack.Render(*this);
        if (_externalCloseRequested) {
            ImGuiMCP::PopStyleColor(5);
            ImGuiMCP::PopStyleVar(2);
            Destroy();
            return;
        }
        switch (_activePanel) {
        case PanelId::kThreadConfig:
            _elements->threadConfigPanel.Render(*this);
            break;
        case PanelId::kSceneSelect:
            _elements->sceneSelectPanel.Render(*this);
            break;
        case PanelId::kOffsetAdjust:
            _elements->offsetAdjustPanel.Render(*this);
            break;
        case PanelId::kElementControl:
            _elements->elementCtrlPanel.Render(*this);
            break;
        default:
            break;
        }
        _elements->elementCtrlPanel.RenderThemeEditor(*this);
        ImGuiMCP::PopStyleColor(5);
        ImGuiMCP::PopStyleVar(2);
    }

    void SceneHUD::SetFocus(bool a_focused)
    {
        if (a_focused && (!_elements || !IsActive()))
            return;
        if (_focused == a_focused)
            return;

        _focused = a_focused;
        _window.SetBlocksInput(a_focused);
        if (!a_focused)
            CloseAllPanels();
    }

    void SceneHUD::CloseAllPanels()
    {
        if (_elements) {
            switch (_activePanel) {
            case PanelId::kThreadConfig:
                _elements->threadConfigPanel.Close();
                break;
            case PanelId::kSceneSelect:
                _elements->sceneSelectPanel.Close();
                break;
            case PanelId::kOffsetAdjust:
                _elements->offsetAdjustPanel.Close();
                break;
            case PanelId::kElementControl:
                _elements->elementCtrlPanel.Close();
                break;
            default:
                break;
            }
        }
        _activePanel = PanelId::kNone;
    }

    void SceneHUD::OpenPanel(PanelId a_panel)
    {
        if (!_elements || !_focused)
            return;
        if (_activePanel == a_panel) {
            CloseAllPanels();
            return;
        }

        CloseAllPanels();
        switch (a_panel) {
        case PanelId::kThreadConfig:
            _elements->threadConfigPanel.Open(*this);
            break;
        case PanelId::kSceneSelect:
            _elements->sceneSelectPanel.Open(*this);
            break;
        case PanelId::kOffsetAdjust:
            _elements->offsetAdjustPanel.Open(*this);
            break;
        case PanelId::kElementControl:
            _elements->elementCtrlPanel.Open(*this);
            break;
        default:
            return;
        }
        _activePanel = a_panel;
    }

    bool SceneHUD::PrepareSceneSelect(RE::TESQuest* a_quest)
    {
        if (!a_quest || _speedThread != a_quest || !Instance::GetInstance(a_quest) ||
            !_registered || !_renderEnabled || RE::UI::GetSingleton()->GameIsPaused())
            return false;
        if (IsActive() && !GetForThread(a_quest))
            return false;
        if (!IsActive())
            Init(a_quest);
        return GetForThread(a_quest) && _elements && _threadScript;
    }

    bool SceneHUD::OpenSceneSelect(RE::TESQuest* a_quest)
    {
        if (!a_quest || _speedThread != a_quest || !GetForThread(a_quest) ||
            !Instance::GetInstance(a_quest) || !_elements || !_focused || !ShouldRender())
            return false;
        // OpenPanel toggles an already-open panel; the hotkey must be idempotent.
        if (!IsPanelOpen(PanelId::kSceneSelect))
            OpenPanel(PanelId::kSceneSelect);
        return IsPanelOpen(PanelId::kSceneSelect);
    }

    bool SceneHUD::OpenExternalSceneSelect(RE::TESQuest* a_quest)
    {
        if (!a_quest || !_registered || !_renderEnabled || RE::UI::GetSingleton()->GameIsPaused())
            return false;
        auto script = Script::GetScriptObject(a_quest, "sslThreadController");
        auto* instance = Instance::GetInstance(a_quest);
        if (!script || script->currentState != "Animating" || !instance || !instance->GetActiveScene() || !instance->GetActiveStage())
            return false;
        if (_externalSceneSelect && GetForThread(a_quest)) {
            if (_externalCloseRequested)
                return false;
            if (!IsPanelOpen(PanelId::kSceneSelect))
                OpenPanel(PanelId::kSceneSelect);
            return IsPanelOpen(PanelId::kSceneSelect) &&
                IsExternalSceneSelectCurrent(a_quest, GetExternalSceneSelectTicket());
        }
        // Never replace another HUD/control owner, including a hidden player HUD.
        if (IsActive() || _speedThread)
            return false;
        Init(a_quest, false);
        if (!GetForThread(a_quest) || !_elements || !_threadScript) {
            Destroy();
            return false;
        }
        SetFocus(true);
        OpenPanel(PanelId::kSceneSelect);
        return IsExternalSceneSelectCurrent(a_quest, GetExternalSceneSelectTicket());
    }

    bool SceneHUD::IsExternalSceneSelectCurrent(RE::TESQuest* a_quest, int a_ticket) const
    {
        return a_ticket >= 0 && _externalSceneSelect && a_quest && a_quest == _linkedThread &&
            a_ticket == GetExternalSceneSelectTicket() && _focused && _elements && _threadScript &&
            _threadScript->currentState == "Animating" && Instance::GetInstance(a_quest);
    }

    bool SceneHUD::CloseExternalSceneSelect(RE::TESQuest* a_quest, int a_ticket)
    {
        if (!_externalSceneSelect || !a_quest || _linkedThread != a_quest ||
            (a_ticket >= 0 && a_ticket != GetExternalSceneSelectTicket()))
            return false;
        Destroy();
        return true;
    }

    void SceneHUD::UpdateStageTimer(float a_duration, float a_timer)
    {
        if (_elements)
            _elements->animSpeedOverlay.UpdateStageTimer(a_duration, a_timer);
    }

    void SceneHUD::UpdateHighlightedPartner(RE::Actor* a_partner)
    {
        if (_elements)
            _elements->enjoymentBarsOverlay.UpdateHighlightedPartner(a_partner);
    }

    void SceneHUD::UpdateEnjoyment(RE::Actor* a_actor, float a_enjoyment, RE::BSFixedString a_interactions)
    {
        if (_elements)
            _elements->enjoymentBarsOverlay.UpdateSlider(a_actor, a_enjoyment, a_interactions);
    }

    void SceneHUD::RegisterRaiseEnjoymentAttempt(RE::Actor* a_actor, float a_nextTimeCycle)
    {
        if (!_elements)
            return;
        auto* instance = GetThreadInstance();
        if (instance && instance->GetThreadProperty<bool>("ElementUI_EnjBars") &&
            instance->GetThreadProperty<bool>("VarUI_SeparateOrgasm")) {
            _elements->enjoymentBarsOverlay.RegisterRaiseEnjAttempt(*this, a_actor, a_nextTimeCycle);
        }
    }

    void SceneHUD::RefreshStageOffsets()
    {
        if (_elements && _activePanel == PanelId::kOffsetAdjust)
            _elements->offsetAdjustPanel.RefreshStageOffsets(*this);
    }

    void SceneHUD::RebuildSceneList()
    {
        if (!_elements)
            return;
        _elements->sceneSelectPanel.RebuildEntries(*this);
        _elements->sceneSelectPanel.RebuildFilter();
    }

    bool SceneHUD::IsDebugNodeDrawEnabled() const
    {
        if (!_elements)
            return false;
        auto* instance = GetThreadInstance();
        return instance && instance->GetThreadProperty<bool>("ElementUI_DebugNodeDraw");
    }

    void SceneHUD::DebugNodeDrawBeginFrame()
    {
        if (_elements)
            _elements->debugNodeDraw.BeginFrame();
    }

    void SceneHUD::DebugNodeDrawPublish()
    {
        if (_elements)
            _elements->debugNodeDraw.Publish();
    }

    void SceneHUD::DebugNodeDrawAddRing(const RE::NiPoint3& a_center, const RE::NiPoint3& a_right, const RE::NiPoint3& a_up, float a_radius)
    {
        if (_elements)
            _elements->debugNodeDraw.AddRing(a_center, a_right, a_up, a_radius);
    }

    void SceneHUD::DebugNodeDrawAddTaperedCapsule(const RE::NiPoint3& a_start, const RE::NiPoint3& a_end, float a_startRadius, float a_endRadius)
    {
        if (_elements)
            _elements->debugNodeDraw.AddTaperedCapsule(a_start, a_end, a_startRadius, a_endRadius);
    }
}
