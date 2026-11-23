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
        bool Open(RE::TESQuest* a_quest, uint64_t a_ticket, std::vector<Item> a_items);
        void Close(RE::TESQuest* a_quest, uint64_t a_ticket = 0);

      private:
        FurnSelectMenu() = default;

        static void __stdcall RenderCallback();
        void Render();
        void HandleSelection(std::size_t a_index, uint64_t a_ticket);

        RE::TESQuest* _linkedThread{};
        uint64_t _ticket{ 0 };
        std::mutex _mutex;
        std::vector<Item> _items;
    };
}
