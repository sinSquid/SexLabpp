#pragma once

#include <cmath>
#include <limits>

namespace Script
{
    using VM = RE::BSScript::Internal::VirtualMachine;
    using ObjectPtr = RE::BSTSmartPointer<RE::BSScript::Object>;
    using ArrayPtr = RE::BSTSmartPointer<RE::BSScript::Array>;
    using TypePtr = RE::BSTSmartPointer<RE::BSScript::ObjectTypeInfo>;
    using CallbackPtr = RE::BSTSmartPointer<RE::BSScript::IStackCallbackFunctor>;
    using Args = RE::BSScript::IFunctionArguments;
    using RawType = RE::BSScript::TypeInfo::RawType;

    inline RE::VMHandle GetHandle(const RE::TESForm* a_form)
    {
        auto vm = VM::GetSingleton();
        auto policy = vm->GetObjectHandlePolicy();
        return policy->GetHandleForObject(a_form->GetFormType(), a_form);
    }

    inline ObjectPtr GetScriptObject(const RE::TESForm* a_form, const char* a_class, bool a_create = false)
    {
        if (!a_form || !a_class || !*a_class)
            return nullptr;
        auto vm = VM::GetSingleton();
        auto handle = GetHandle(a_form);

        ObjectPtr object = nullptr;
        bool found = vm->FindBoundObject(handle, a_class, object);
        if (!found && a_create) {
            vm->CreateObject2(a_class, object);
            if (object)
                vm->BindObject(object, handle, false);
        }

        return object;
    }

    template <class T>
    inline T GetProperty(ObjectPtr a_obj, const RE::BSFixedString& a_prop)
    {
        auto var = a_obj ? a_obj->GetProperty(a_prop) : nullptr;
        if (!var) {
            logger::error("Unable to read script property: {}", a_prop.c_str());
            return T{};
        }
        return RE::BSScript::UnpackValue<T>(var);
    }

    template <class T, typename = std::enable_if_t<std::is_integral_v<T> || std::is_floating_point_v<T>>>
    inline T GetTrivialProperty(ObjectPtr a_obj, const RE::BSFixedString& a_prop)
    {
        const auto var = a_obj ? a_obj->GetProperty(a_prop) : nullptr;
        if (!var) {
            logger::error("Unable to read script property: {}", a_prop.c_str());
            return T{};
        }
        const auto type = var->GetType().GetRawType();
        switch (type) {
        case RawType::kBool:
            return static_cast<T>(RE::BSScript::UnpackValue<bool>(var));
        case RawType::kInt:
            return static_cast<T>(RE::BSScript::UnpackValue<int>(var));
        case RawType::kFloat:
            {
                const float value = RE::BSScript::UnpackValue<float>(var);
                if (!std::isfinite(value)) {
                    logger::error("Non-finite script property: {}", a_prop.c_str());
                    return T{};
                }
                if constexpr (std::is_integral_v<T> && !std::is_same_v<T, bool>) {
                    const auto truncated = std::trunc(static_cast<long double>(value));
                    // The exclusive power-of-two bound stays exact even where
                    // long double has double precision (MSVC's 64-bit integers).
                    const auto upper = std::ldexp(1.0L, std::numeric_limits<T>::digits);
                    if (truncated < static_cast<long double>(std::numeric_limits<T>::lowest()) || truncated >= upper) {
                        logger::error("Out-of-range script property: {}", a_prop.c_str());
                        return T{};
                    }
                }
                return static_cast<T>(value);
            }
        default:
            logger::error("Not a trivial type: {}", std::to_underlying(type));
            break;
        }
        return 0;
    }

    template <class T>
    inline void SetProperty(ObjectPtr a_obj, const RE::BSFixedString& a_prop, T a_val)
    {
        auto var = a_obj ? a_obj->GetProperty(a_prop) : nullptr;
        if (!var) {
            logger::error("Unable to write script property: {}", a_prop.c_str());
            return;
        }
        RE::BSScript::PackValue(var, a_val);
    }

    inline bool DispatchMethodCall(ObjectPtr a_obj, const RE::BSFixedString& a_fnName, CallbackPtr a_callback, Args* a_args)
    {
        auto vm = VM::GetSingleton();
        return vm->DispatchMethodCall(a_obj, a_fnName, a_args, a_callback);
    }

    template <class... Args>
    inline bool DispatchMethodCall(ObjectPtr a_obj, const RE::BSFixedString& a_fnName, CallbackPtr a_callback, Args&&... a_args)
    {
        auto args = RE::MakeFunctionArguments(std::forward<Args>(a_args)...);
        return DispatchMethodCall(a_obj, a_fnName, a_callback, args);
    }

    inline bool DispatchStaticCall(const RE::BSFixedString& a_class, const RE::BSFixedString& a_fnName, CallbackPtr a_callback, Args* a_args)
    {
        auto vm = VM::GetSingleton();
        return vm->DispatchStaticCall(a_class, a_fnName, a_args, a_callback);
    }

    template <class... Args>
    inline bool DispatchStaticCall(const RE::BSFixedString& a_class, const RE::BSFixedString& a_fnName, CallbackPtr a_callback, Args&&... a_args)
    {
        auto args = RE::MakeFunctionArguments(std::forward<Args>(a_args)...);
        return DispatchStaticCall(a_class, a_fnName, a_callback, args);
    }
}
