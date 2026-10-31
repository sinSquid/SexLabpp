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
        void Open(RE::TESQuest* a_quest, const std::vector<Item>& a_items);
        void CancelForThread(RE::TESQuest* a_quest);

      private:
        FurnSelectMenu() = default;

        static void __stdcall RenderCallback();
        void Render();
        void HandleSelection(std::size_t a_index);

        RE::TESQuest* _linkedThread{};
        std::int32_t _ownerRevision{};
        std::vector<Item> _items;
    };
}
