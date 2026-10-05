#include "FurnSelectMenu.h"
#include "SceneHUD.h"

namespace Thread::Interface
{
    using UI::SetWindowFontSize;

    FurnSelectMenu& FurnSelectMenu::GetSingleton()
    {
        static FurnSelectMenu singleton;
        return singleton;
    }

    void FurnSelectMenu::Revert()
    {
        const std::scoped_lock lock{ _stateMutex };
        Hide();
        _linkedThread = nullptr;
        _startupRequest = 0;
        _items.clear();
    }

    bool FurnSelectMenu::Register()
    {
        if (!RegisterWindow(RenderCallback, true)) {
            logger::error("FurnSelectMenu::Register >> AddWindow failed");
            return false;
        }
        return true;
    }

    void FurnSelectMenu::Open(RE::TESQuest* a_quest, const std::vector<Item>& a_items, int32_t a_request)
    {
        std::scoped_lock lock{ _stateMutex };
        if (!a_quest)
            return;
        if (IsVisible() && (_linkedThread != a_quest || _startupRequest != a_request))
            throw std::runtime_error("Another center selection menu is already open.");
        _linkedThread = a_quest;
        _startupRequest = a_request;
        _items = a_items;
        Show();
        if (!IsVisible())
            throw std::runtime_error("Center selection window is unavailable.");
    }

    void FurnSelectMenu::Cancel(RE::TESQuest* a_quest, int32_t a_request)
    {
        std::scoped_lock lock{ _stateMutex };
        if (_linkedThread != a_quest || _startupRequest != a_request)
            return;
        Hide();
        _linkedThread = nullptr;
        _items.clear();
    }

    void FurnSelectMenu::HandleSelection(std::size_t a_index)
    {
        Hide();
        auto* quest = std::exchange(_linkedThread, nullptr);
        _items.clear();
        if (!quest)
            return;
        const auto request = _startupRequest;
        const auto generation = Instance::GetWorldGeneration();
        SKSE::GetTaskInterface()->AddTask([quest, request, a_index, generation]() {
            if (Instance::GetWorldGeneration() != generation)
                return;
            auto inst = Instance::GetPendingInstance(quest);
            if (!inst || !inst->IsStartupRequest(request))
                return;
            inst->SetCenterRefSelected(a_index);
        });
    }

    void __stdcall FurnSelectMenu::RenderCallback()
    {
        GetSingleton().Render();
    }

    void FurnSelectMenu::Render()
    {
        std::scoped_lock lock{ _stateMutex };
        if (!IsVisible())
            return;
        auto& scale = SceneHUD::GetSingleton().GetScale();

        const float panelW = scale.Px(300.0f);
        const float padH = scale.Px(12.0f);
        const float padV = scale.Px(5.0f);
        const float rowH = scale.TextPx(UI::Theme::FontSize.body) + padV * 2.0f;

        // Centred on screen
        auto* vp = ImGuiMCP::GetMainViewport();
        const ImGuiMCP::ImVec2 centre = ImGuiMCP::ImGuiViewportManager::GetCenter(vp);
        ImGuiMCP::SetNextWindowPos(centre, ImGuiMCP::ImGuiCond_Always, ImGuiMCP::ImVec2{ 0.5f, 0.5f });
        ImGuiMCP::SetNextWindowSize({ panelW, 0.0f }, ImGuiMCP::ImGuiCond_Always);
        ImGuiMCP::SetNextWindowBgAlpha(0.6f);

        // Begin() needs a plain bool*, so mirror the window's atomic IsOpen through a local and write it back afterward.
        bool isOpen = true;
        constexpr auto kFlags =
            ImGuiMCP::ImGuiWindowFlags_NoTitleBar | ImGuiMCP::ImGuiWindowFlags_NoResize |
            ImGuiMCP::ImGuiWindowFlags_NoMove | ImGuiMCP::ImGuiWindowFlags_NoCollapse |
            ImGuiMCP::ImGuiWindowFlags_AlwaysAutoResize;

        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_WindowBg, UI::Theme::Color.panelBackground);
        ImGuiMCP::PushStyleColor(ImGuiMCP::ImGuiCol_Border, UI::Theme::Color.panelBorder);
        if (!ImGuiMCP::Begin("##slpp_FurnSelect", &isOpen, kFlags)) {
            ImGuiMCP::End();
            ImGuiMCP::PopStyleColor(2);
            SetVisible(isOpen);
            return;
        }

        // Panel title
        SetWindowFontSize(scale.TextPx(UI::Theme::FontSize.sectionHeader));
        const char* title = "SELECT SCENE CENTER";
        ImGuiMCP::SetCursorPosX((panelW - ImGuiMCP::CalcTextSize(title).x) * 0.5f);
        ImGuiMCP::TextColored(UI::Theme::ToVec4(UI::Theme::Color.textSecondary), "%s", title);
        ImGuiMCP::Dummy(ImGuiMCP::ImVec2{ 0.0f, scale.Px(2.0f) });
        ImGuiMCP::Separator();
        ImGuiMCP::Dummy(ImGuiMCP::ImVec2{ 0.0f, scale.Px(2.0f) });

        SetWindowFontSize(scale.TextPx(UI::Theme::FontSize.body));
        std::optional<std::size_t> selectedIndex;

        if (_items.empty()) {
            ImGuiMCP::SetCursorPosX(padH);
            ImGuiMCP::TextColored(UI::Theme::ToVec4(UI::Theme::Color.textMuted), "No suitable scene center nearby.");
        } else {
            const float innerW = panelW - padH * 2.0f;

            for (std::size_t i = 0; i < _items.size(); ++i) {
                ImGuiMCP::PushID(static_cast<int>(i));

                const ImGuiMCP::ImVec2 rowMin = ImGuiMCP::GetCursorScreenPos();
                ImGuiMCP::SetCursorPosX(padH);
                if (UI::SelectableButton("##slpp_furn_row", false,
                        ImGuiMCP::ImGuiSelectableFlags_AllowOverlap,
                        ImGuiMCP::ImVec2{ innerW, rowH }))
                    selectedIndex = i;
                const bool hov = ImGuiMCP::IsItemHovered();

                const std::string& baseName = _items[i].name;
                const std::string& subType = _items[i].type;
                const std::string& formId = _items[i].formId;

                std::string leftLabel;
                if (!baseName.empty() && !subType.empty())
                    leftLabel = baseName + " (" + subType + ")";
                else if (!baseName.empty())
                    leftLabel = baseName;
                else
                    leftLabel = subType;

                ImGuiMCP::SetCursorScreenPos({ rowMin.x + padH, rowMin.y + padV });
                ImGuiMCP::TextColored(
                    UI::Theme::ToVec4(hov ? UI::Theme::Color.textPrimary : UI::Theme::Color.textSecondary),
                    "%s", leftLabel.c_str());

                if (!formId.empty()) {
                    const float fW = ImGuiMCP::CalcTextSize(formId.c_str()).x;
                    ImGuiMCP::SetCursorScreenPos({ rowMin.x + padH + innerW - fW - padH, rowMin.y + padV });
                    ImGuiMCP::TextColored(UI::Theme::ToVec4(UI::Theme::Color.textMuted), "%s", formId.c_str());
                }

                ImGuiMCP::SetCursorScreenPos({ rowMin.x, rowMin.y + rowH });
                ImGuiMCP::PopID();
            }
        }

        ImGuiMCP::Dummy(ImGuiMCP::ImVec2{ 0.0f, scale.Px(2.0f) });
        ImGuiMCP::SetWindowFontScale(1.0f);
        ImGuiMCP::End();
        ImGuiMCP::PopStyleColor(2);
        SetVisible(isOpen);
        if (selectedIndex)
            HandleSelection(*selectedIndex);
    }
}
