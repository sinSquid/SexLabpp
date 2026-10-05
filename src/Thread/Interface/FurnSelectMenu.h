#pragma once
#include "Thread/Interface/UI/Window.h"

namespace Thread::Interface
{
    class FurnSelectMenu final : public UI::WindowComponent
    {
      public:
        struct Item
        {
            std::string name;
            std::string type;
            std::string formId;
        };

        static FurnSelectMenu& GetSingleton();

        bool Register();
        void Revert();
        void Open(RE::TESQuest* a_quest, const std::vector<Item>& a_items, int32_t a_request);
        void Cancel(RE::TESQuest* a_quest, int32_t a_request);

      private:
        FurnSelectMenu() = default;

        static void __stdcall RenderCallback();
        void Render();
        void HandleSelection(std::size_t a_index);

        RE::TESQuest* _linkedThread{};
        int32_t _startupRequest{};
        std::mutex _stateMutex;
        std::vector<Item> _items;
    };
}
