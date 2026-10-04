#include "Scale.h"

namespace Registry
{
    float Scale::GetScale(RE::TESObjectREFR* a_reference)
    {
        assert(a_reference);
        const auto node = a_reference->GetNodeByName(basenode);
        const auto baseScale = a_reference->GetScale();
        const auto nodeScale = node ? node->local.scale : 1.0f;
        const auto retVal = baseScale * nodeScale;
        logger::debug("GetScale: {:X} -> Base = {}, Skeleton = {} => {}", a_reference->GetFormID(), baseScale, nodeScale, retVal);
        return retVal;
    }

    void Scale::SetScale(RE::Actor* a_actor, float a_absolutescale)
    {
        SetScale(a_actor, { a_actor }, a_absolutescale);
    }

    void Scale::SetScale(RE::Actor* a_actor, RaceKey a_racekey, float a_absolutescale)
    {
        assert(a_actor && a_absolutescale > 0.0f);
        if (Settings::bDisableScale) {
            return;
        } else if (!transformInterface) {
            logger::error("Missing interface, scaling disabled");
            Settings::bDisableScale = true;
            return;
        }
        switch (a_racekey) {
        case RaceKey::AshHopper:
            // a_absolutescale *= 0.5f;
            break;
        case RaceKey::Chaurus:
            a_absolutescale *= 0.5f;
            break;
        case RaceKey::ChaurusHunter:
            // a_absolutescale *= 0.69f;
            break;
        case RaceKey::Chicken:
            // a_absolutescale *= 1.3f;
            break;
        case RaceKey::Fox:
            // a_absolutescale *= 0.72f;
            break;
        case RaceKey::FrostAtronach:
            // a_absolutescale *= 1.3f;
            break;
        case RaceKey::Spider:
            a_absolutescale *= 0.75f;
            break;
        case RaceKey::LargeSpider:
            a_absolutescale *= 1.2f;
            break;
        case RaceKey::GiantSpider:
            a_absolutescale *= 1.9f;
            break;
        case RaceKey::Horker:
            // a_absolutescale *= 1.2f;
            break;
        case RaceKey::Mudcrab:
            // a_absolutescale *= 0.75f;
            break;
        default:
            // a_absolutescale *= 1.0f;
            break;
        }
        float basescale = GetScale(a_actor);
        if (std::abs(basescale - a_absolutescale) < 0.03) {
            logger::debug("Attempted Node Transform to Actor = {:X}, Scale = {} -> {}", a_actor->GetFormID(), basescale, a_absolutescale);
            return;
        }

        const auto base = a_actor->GetActorBase();
        const auto female = base ? base->GetSex() == RE::SEXES::kFemale : false;
        if (transformInterface->GetVersion() < SKEE::INiTransformInterface::Version) {
            const auto legacyInterface = reinterpret_cast<SKEE::Legacy::INiTransformInterface*>(transformInterface);
            const SKEE::Legacy::FixedString node(basenode);
            const SKEE::Legacy::FixedString name(namekey);
            SKEE::Legacy::OverrideVariant scaleMode;
            scaleMode.SetInt(SKEE::Legacy::OverrideVariant::ScaleMode, ScaleModes::Multiplicative);
            legacyInterface->AddNodeTransform(a_actor, false, female, node, name, scaleMode);
            if (legacyInterface->RemoveNodeTransformComponent(a_actor, false, female, node, name, SKEE::Legacy::OverrideVariant::Scale, 0)) {
                legacyInterface->UpdateNodeTransforms(a_actor, false, female, node);
                basescale = GetScale(a_actor);
            }
            // base * x = absolute <=> x = absolute / base
            const float scale = a_absolutescale / basescale;
            logger::debug("Applying Node Transform to Actor = {:X}, Scale = {} -> {}, x = {}", a_actor->GetFormID(), basescale, a_absolutescale, scale);
            SKEE::Legacy::OverrideVariant scaleOverride;
            scaleOverride.SetFloat(SKEE::Legacy::OverrideVariant::Scale, scale);
            legacyInterface->AddNodeTransform(a_actor, false, female, node, name, scaleOverride);
            legacyInterface->UpdateNodeTransforms(a_actor, false, female, node);
        } else {
            const auto modernInterface = static_cast<SKEE::INiTransformInterface*>(transformInterface);
            modernInterface->AddNodeTransformScaleMode(a_actor, false, female, basenode, namekey, ScaleModes::Multiplicative);
            if (modernInterface->RemoveNodeTransformScale(a_actor, false, female, basenode, namekey)) {
                modernInterface->UpdateNodeTransforms(a_actor, false, female, basenode);
                basescale = GetScale(a_actor);
            }

            const float scale = a_absolutescale / basescale;
            logger::debug("Applying Node Transform to Actor = {:X}, Scale = {} -> {}, x = {}", a_actor->GetFormID(), basescale, a_absolutescale, scale);
            modernInterface->AddNodeTransformScale(a_actor, false, female, basenode, namekey, scale);
            modernInterface->UpdateNodeTransforms(a_actor, false, female, basenode);
        }
    }

    void Scale::RemoveScale(RE::Actor* a_actor)
    {
        assert(a_actor);
        if (Settings::bDisableScale) {
            return;
        } else if (!transformInterface) {
            logger::error("Missing interface, scaling disabled");
            Settings::bDisableScale = true;
            return;
        }

        const auto base = a_actor->GetActorBase();
        const auto female = base ? base->GetSex() == RE::SEXES::kFemale : false;
        if (transformInterface->GetVersion() < SKEE::INiTransformInterface::Version) {
            const auto legacyInterface = reinterpret_cast<SKEE::Legacy::INiTransformInterface*>(transformInterface);
            const SKEE::Legacy::FixedString node(basenode);
            const SKEE::Legacy::FixedString name(namekey);
            if (!legacyInterface->RemoveNodeTransformComponent(a_actor, false, female, node, name, SKEE::Legacy::OverrideVariant::Scale, 0)) {
                return;
            }
            logger::debug("Removed Transform Scale from {:X}", a_actor->GetFormID());
            legacyInterface->UpdateNodeTransforms(a_actor, false, female, node);
        } else {
            const auto modernInterface = static_cast<SKEE::INiTransformInterface*>(transformInterface);
            if (modernInterface->RemoveNodeTransformScale(a_actor, false, female, basenode, namekey)) {
                logger::debug("Removed Transform Scale from {:X}", a_actor->GetFormID());
                modernInterface->UpdateNodeTransforms(a_actor, false, female, basenode);
            }
        }
    }

}  // namespace Registry
