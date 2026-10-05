#pragma once

namespace Util
{
    inline bool IsGamePausedOrFrozen()
    {
        const bool freezeTime = *reinterpret_cast<const bool*>(reinterpret_cast<const std::byte*>(RE::Main::GetSingleton()) + (REL::Module::IsVR() ? 0x0E : 0x16));
        return RE::UI::GetSingleton()->GameIsPaused() || freezeTime;
    }

    inline void PrintConsole(const std::string& a_str)
    {
        const auto console = RE::ConsoleLog::GetSingleton();
        if (a_str.empty())
            return;
        else if (a_str.size() < 1000)
            console->Print("%s", a_str.c_str());
        else {  // Large strings printed to console crash the game - truncate it
            size_t i = 0;
            do {
                constexpr auto maxchar = 950;
                auto print = a_str.substr(i, maxchar);
                print += '\n';
                i += maxchar;
                console->Print("%s", print.c_str());
            } while (i < a_str.size());
        }
    }

    inline RE::TESActorBase* GetLeveledActorBase(RE::Actor* a_actor)
    {
        const auto base = a_actor->GetTemplateActorBase();
        return base ? base : a_actor->GetActorBase();
    }

    // using _GetFormEditorID = const char* (*)(std::uint32_t);
    // inline std::string GetEditorID(RE::TESForm* a_form)
    // {
    // 	static auto tweaks = GetModuleHandle("po3_Tweaks");
    // 	static auto func = reinterpret_cast<_GetFormEditorID>(GetProcAddress(tweaks, "GetFormEditorID"));
    // 	if (func) {
    // 		return func(a_form->formID);
    // 	}
    // 	return {};
    // }
}
