#include "Animation.h"

#include "Registry/Define/RaceKey.h"
#include "Registry/Library.h"
#include "Registry/Util/Decode.h"
#include "Util/Assignment.h"
#include "Util/Combinatorics.h"
#include "Util/StringUtil.h"

namespace Registry
{
    AnimPackage::AnimPackage(const fs::path a_file)
    {
        std::ifstream file(a_file, std::ios::binary);
        file.exceptions(std::fstream::badbit | std::fstream::failbit);
        Decode::Reader stream(file);

        uint8_t version;
        constexpr uint8_t MIN_VERSION = 1;
        constexpr uint8_t MAX_VERSION = 4;
        stream.read(reinterpret_cast<char*>(&version), 1);
        if (version < MIN_VERSION || version > MAX_VERSION) {
            const auto err = std::format("Invalid version: {}", version);
            throw std::runtime_error(err.c_str());
        }
        Decode::Read(stream, name);
        Decode::Read(stream, author);
        hash.resize(Decode::HASH_SIZE);
        stream.read(hash.data(), Decode::HASH_SIZE);

        uint64_t scene_count;
        Decode::Read(stream, scene_count);
        Decode::ValidateCount(stream, scene_count, 16, Decode::MAX_SCENES);
        scenes.reserve(scene_count);
        for (size_t i = 0; i < scene_count; i++) {
            scenes.push_back(std::make_unique<Scene>(stream, hash, version));
        }
    }

    Scene::Scene(Decode::Reader& a_stream, std::string_view a_hash, uint8_t a_version) :
      hash(a_hash), enabled(true)
    {
        // initialize start_animation to avoid crash
        start_animation = nullptr;

        id.resize(Decode::ID_SIZE);
        a_stream.read(id.data(), Decode::ID_SIZE);
        Decode::Read(a_stream, name);
        // --- Position Infos
        uint64_t info_count;
        Decode::Read(a_stream, info_count);
        Decode::ValidateCount(a_stream, info_count, 7, ActorFragment::MAX_ACTOR_COUNT);
        if (info_count == 0 || info_count > ActorFragment::MAX_ACTOR_COUNT)
            throw std::runtime_error("Invalid scene position count");
        positions.reserve(info_count);
        for (size_t i = 0; i < info_count; i++) {
            positions.emplace_back(a_stream, a_version);
        }

        enum legacySex : char
        {
            Male = 'M',
            Female = 'F',
            Futa = 'H',
            Creature = 'C',
        };
        std::vector<std::vector<legacySex>> sexes{};
        sexes.reserve(positions.size());
        for (auto&& position : positions) {
            std::vector<legacySex> vec{};
            if (position.data.IsHuman()) {
                if (position.data.IsSex(Sex::Male))
                    vec.push_back(legacySex::Male);
                if (position.data.IsSex(Sex::Female))
                    vec.push_back(legacySex::Female);
                if (position.data.IsSex(Sex::Futa))
                    vec.push_back(legacySex::Futa);
            } else {
                vec.push_back(legacySex::Creature);
            }
            if (vec.empty()) {
                const auto err = std::format("Some position has no associated sex in scene: {}", id);
                throw std::runtime_error(err.c_str());
            }
            sexes.push_back(vec);
        }
        Combinatorics::ForEachCombination(sexes, [&](auto& it) {
            std::vector<char> gender_tag{};
            for (auto&& sex : it) {
                gender_tag.push_back(*sex);
            }
            RE::BSFixedString gTag1{ std::string{ gender_tag.begin(), gender_tag.end() } };
            RE::BSFixedString gTag2{ std::string{ gender_tag.rbegin(), gender_tag.rend() } };
            tags.AddTag(gTag1);
            if (gTag2 != gTag1) {
                tags.AddTag(gTag2);
            }
            return Combinatorics::CResult::Next;
        });
        // --- Stages
        std::string startstage(Decode::ID_SIZE, 'X');
        if (a_version < 4) {
            a_stream.read(startstage.data(), Decode::ID_SIZE);
        }
        uint64_t stage_count;
        Decode::Read(a_stream, stage_count);
        Decode::ValidateCount(a_stream, stage_count, 16, 4096);
        if (stage_count == 0 || stage_count > 4096)
            throw std::runtime_error("Invalid animation stage count");
        stages.reserve(stage_count);
        std::set<std::string> stageIDs;
        for (size_t i = 0; i < stage_count; i++) {
            const auto& stage = stages.emplace_back(
                std::make_unique<Stage>(a_stream, a_version));

            if (stage->positions.size() != positions.size() || !stageIDs.insert(stage->id).second)
                throw std::runtime_error("Inconsistent stage positions or duplicate stage ID");
            tags.AddTag(stage->tags);
            if (stage->id == startstage) {
                start_animation = stage.get();
            }
        }
        if (!start_animation && stages.size() == 0) {
            const auto err = std::format("Start animation {} is not found in scene {}", startstage, id);
            throw std::runtime_error(err.c_str());
        }
        if (!start_animation) {
            start_animation = stages[0].get();
        }
        // --- Graph
        uint64_t graph_vertices;
        Decode::Read(a_stream, graph_vertices);
        Decode::ValidateCount(a_stream, graph_vertices, 16, 4096);
        if (graph_vertices != stage_count) {
            const auto err = std::format("Invalid graph vertex count; expected {} but got {}", stage_count, graph_vertices);
            throw std::runtime_error(err.c_str());
        }
        std::string vertexid(Decode::ID_SIZE, 'X');
        for (size_t i = 0; i < graph_vertices; i++) {
            a_stream.read(vertexid.data(), Decode::ID_SIZE);
            const auto vertex = GetStageByID(vertexid.data());
            if (!vertex) {
                const auto err = std::format("Invalid vertex: {} in scene: {}", vertexid, id);
                throw std::runtime_error(err.c_str());
            }
            std::vector<const Stage*> edges{};
            uint64_t edge_count;
            Decode::Read(a_stream, edge_count);
            Decode::ValidateCount(a_stream, edge_count, 8, 4096);
            if (edge_count > stage_count)
                throw std::runtime_error("Invalid animation edge count");
            std::string edgeid(Decode::ID_SIZE, 'X');
            for (size_t n = 0; n < edge_count; n++) {
                a_stream.read(edgeid.data(), Decode::ID_SIZE);
                const auto edge = GetStageByID(edgeid.data());
                if (!edge) {
                    const auto err = std::format("Invalid edge: {} for vertex: {} in scene: {}", edgeid, vertexid, id);
                    throw std::runtime_error(err.c_str());
                }
                edges.push_back(edge);
            }
            if (!graph.emplace(vertex, std::move(edges)).second)
                throw std::runtime_error("Duplicate animation graph vertex");
        }
        // --- Misc
        uint32_t furniture;
        Decode::Read(a_stream, furniture);
        // All is a published sentinel; bits 27..31 otherwise have no meaning.
        if (furniture != uint32_t(FurnitureType::All) && (furniture & ~((uint32_t(FurnitureType::Pillory) << 1) - 1)))
            throw std::runtime_error("Invalid SLR furniture mask");
        furnitureTypes = REX::EnumSet<FurnitureType::Value>{ FurnitureType::Value(furniture) };
        Decode::Read(a_stream, allowBed);
        furnitureOffset = Coordinate(a_stream);
        Decode::Read(a_stream, isPrivate);
        if (!a_stream)
            throw std::runtime_error("Truncated animation scene");
    }

    PositionInfo::PositionInfo(Decode::Reader& a_stream, uint8_t a_version)
    {
        enum Extra : uint8_t
        {
            Submissive = 1 << 0,
            Vampire = 1 << 1,
            Unconscious = 1 << 2
        };
        float scale;
        RaceKey race;
        REX::EnumSet<Sex> sex;
        REX::EnumSet<Extra> extra;
        const auto raceByte = Decode::Read<uint8_t>(a_stream);
        const auto sexByte = Decode::Read<uint8_t>(a_stream);
        Decode::Read(a_stream, scale);
        const auto extraByte = Decode::Read<uint8_t>(a_stream);
        race = RaceKey{ RaceKey::Value(raceByte) };
        if (!race.IsValid() || sexByte == 0 || (sexByte & ~uint8_t(7)) ||
            (!race.Is(RaceKey::Human) && (sexByte & uint8_t(Sex::Futa))) ||
            (extraByte & ~uint8_t(7)) || scale <= 0.0f)
            throw std::runtime_error("Invalid SLR position race, sex, extra flags or scale");
        sex = REX::EnumSet<Sex>{ Sex(sexByte) };
        extra = REX::EnumSet<Extra>{ Extra(extraByte) };

        data = ActorFragment(sex, race, scale, extra.all(Extra::Vampire), extra.all(Extra::Submissive), extra.all(Extra::Unconscious));

        if (a_version > 1 && a_version < 4) {
            uint64_t extra_custom;
            Decode::Read(a_stream, extra_custom);
            Decode::ValidateCount(a_stream, extra_custom, 8, Decode::MAX_TAGS);
            annotations.reserve(extra_custom);
            for (size_t j = 0; j < extra_custom; j++) {
                RE::BSFixedString tag;
                Decode::Read(a_stream, tag);
                annotations.push_back(tag);
            }
        } else {
            annotations = {};
        }
    }

    Stage::Stage(Decode::Reader& a_stream, uint8_t a_version)
    {
        id.resize(Decode::ID_SIZE);
        a_stream.read(id.data(), Decode::ID_SIZE);

        uint64_t position_count;
        Decode::Read(a_stream, position_count);
        Decode::ValidateCount(a_stream, position_count, 8, ActorFragment::MAX_ACTOR_COUNT);
        if (position_count == 0 || position_count > ActorFragment::MAX_ACTOR_COUNT)
            throw std::runtime_error("Invalid animation position count");
        positions.reserve(position_count);
        for (size_t i = 0; i < position_count; i++) {
            positions.emplace_back(a_stream, a_version);
        }
        Decode::Read(a_stream, fixedlength);
        if (fixedlength < 0.0f)
            throw std::runtime_error("Invalid negative SLR stage duration");
        Decode::Read(a_stream, navtext);
        tags = TagData{ a_stream };
    }

    Position::Position(Decode::Reader& a_stream, uint8_t a_version) :
      event(Decode::Read<decltype(event)>(a_stream)),
      climax(Decode::Read<uint8_t>(a_stream) > 0),
      offset(Transform(a_stream)),
      strips(decltype(strips)::enum_type(Decode::Read<uint8_t>(a_stream))),
      tags({})
    {
        if (a_version == 3)
            Decode::Read<int8_t>(a_stream);
        if (a_version >= 4) {
            uint64_t extra_custom;
            Decode::Read(a_stream, extra_custom);
            Decode::ValidateCount(a_stream, extra_custom, 8, Decode::MAX_TAGS);
            tags.reserve(extra_custom);
            for (size_t j = 0; j < extra_custom; j++) {
                RE::BSFixedString tag;
                Decode::Read(a_stream, tag);
                tags.push_back(tag);
            }
        }
    }

    void Position::Save(YAML::Node& a_node) const
    {
        auto transform = a_node["transform"];
        offset.Save(transform);
    }

    void Position::Load(const YAML::Node& a_node)
    {
        if (auto transform = a_node["transform"]; transform.IsDefined()) {
            offset.Load(transform);
        }
    }

    void Stage::Save(YAML::Node& a_node) const
    {
        for (auto&& annotation : tags.GetAnnotations()) {
            a_node["annotations"].push_back(annotation.data());
        }
        const auto hasChanges = std::ranges::find_if(positions, [](auto& position) { return position.offset.HasChanges(); });
        if (hasChanges != positions.end()) {
            for (size_t i = 0; i < positions.size(); i++) {
                auto node = a_node[i];
                positions[i].Save(node);
            }
        }
    }

    void Stage::Load(const YAML::Node& a_node)
    {
        if (auto annotations = a_node["annotations"]; annotations.IsDefined()) {
            for (auto&& annotation : annotations) {
                tags.AddAnnotation(annotation.as<std::string>());
            }
        }
        for (size_t i = 0; i < positions.size(); i++) {
            if (auto node = a_node[i]; node.IsDefined()) {
                positions[i].Load(node);
            }
        }
    }

    void Scene::Save(YAML::Node& a_node) const
    {
        a_node["enabled"] = this->enabled;
        auto offset = a_node["furnitureOffset"];
        furnitureOffset.Save(offset);
        a_node["annotations"] = YAML::Node(YAML::NodeType::Sequence);
        for (const auto& annotation : tags.GetAnnotations())
            a_node["annotations"].push_back(annotation.data());
        for (auto&& stage : stages) {
            auto node = a_node[stage->id];
            stage->Save(node);
        }
    }

    void Scene::Load(const YAML::Node& a_node)
    {
        if (const auto offset = a_node["furnitureOffset"]; offset.IsDefined())
            furnitureOffset.Load(offset);
        if (const auto annotations = a_node["annotations"]; annotations.IsDefined()) {
            tags.SetAnnotations({});
            for (const auto& annotation : annotations)
                tags.AddAnnotation(annotation.as<std::string>());
        }
        if (const auto enable = a_node["enabled"]; enable.IsDefined())
            this->enabled = enable.as<bool>();

        for (auto&& stage : stages) {
            if (auto node = a_node[stage->id]; node.IsDefined()) {
                stage->Load(node);
            }
        }
    }


    bool PositionInfo::CanFillPosition(RE::Actor* a_actor) const
    {
        if (!a_actor)
            return false;
        try {
            return CanFillPosition(ActorFragment(a_actor, false));
        } catch (const std::runtime_error& error) {
            logger::warn("Invalid position candidate: {}", error.what());
            return false;
        }
    }

    bool PositionInfo::CanFillPosition(const ActorFragment& a_fragment) const
    {
        return data.GetCompatibilityScore(a_fragment) != 0;
    }

    bool PositionInfo::CanFillPosition(const PositionInfo& a_other) const
    {
        return CanFillPosition(a_other.data);
    }

    bool PositionInfo::HasExtraCstm(const RE::BSFixedString& a_extra) const
    {
        return std::ranges::find(annotations, a_extra) != annotations.end();
    }

    std::string PositionInfo::ConcatExtraCstm() const
    {
        return Util::StringJoin(annotations, ", ");
    }

    PapyrusSex PositionInfo::GetSexPapyrus() const
    {
        auto sex = data.GetSex();
        REX::EnumSet<PapyrusSex> ret{ PapyrusSex::None };
        if (data.IsHuman()) {
#define SET_SEX(s)       \
    if (sex.all(Sex::s)) \
        ret.set(PapyrusSex::s);
            SET_SEX(Male);
            SET_SEX(Female);
            SET_SEX(Futa);
#undef SET_SEX
        } else {
            const auto crtSex = sex.any(Sex::Female) ? PapyrusSex::CrtFemale : PapyrusSex::CrtMale;
            ret.set(crtSex);
        }
        return ret.get();
    }

    REX::EnumSet<FurnitureType::Value> Scene::GetFurnitureTypes() const
    {
        auto ret = furnitureTypes;
        if (allowBed) {
            ret.set(FurnitureType::BedDouble, FurnitureType::BedSingle, FurnitureType::BedRoll);
        }
        return ret;
    }

    Stage* Scene::GetStageByID(const RE::BSFixedString& a_key)
    {
        if (a_key.empty()) {
            return start_animation;
        }
        const auto where = std::find_if(stages.begin(), stages.end(), [&](const std::unique_ptr<Stage>& it) { return a_key == it->id.data(); });
        return where == stages.end() ? nullptr : where->get();
    }

    const Stage* Scene::GetStageByID(const RE::BSFixedString& a_key) const
    {
        if (a_key.empty()) {
            return start_animation;
        }
        const auto where = std::find_if(stages.begin(), stages.end(), [&](const std::unique_ptr<Stage>& it) { return a_key == it->id.data(); });
        return where == stages.end() ? nullptr : where->get();
    }

    bool Scene::HasCreatures() const
    {
        return std::ranges::any_of(positions, [](auto&& info) { return !info.IsHuman(); });
    }

    uint32_t Scene::CountSubmissives() const
    {
        return static_cast<uint32_t>(std::ranges::count_if(positions, [](auto&& info) { return info.IsSubmissive(); }));
    }

    const PositionInfo* Scene::GetNthPosition(size_t n) const
    {
        return &positions.at(n);
    }

    uint32_t Scene::CountPositions() const
    {
        return static_cast<uint32_t>(positions.size());
    }

    bool Scene::IsEnabled() const
    {
        return enabled;
    }

    bool Scene::IsPrivate() const
    {
        return isPrivate;
    }

    bool Scene::IsCompatibleTags(const TagData& a_tags) const
    {
        return this->tags.HasTags(a_tags, true);
    }
    bool Scene::IsCompatibleTags(const TagDetails& a_details) const
    {
        return a_details.MatchTags(tags);
    }

    bool Scene::RequiresFurniture() const
    {
        return furnitureTypes != FurnitureType::None;
    }

    RE::BSFixedString Scene::GetPackageHash() const
    {
        return hash;
    }

    bool Scene::IsCompatibleFurniture(const RE::TESObjectREFR* a_reference) const
    {
        const auto details = Library::GetSingleton()->GetFurnitureDetails(a_reference);
        return IsCompatibleFurniture(details);
    }

    bool Scene::IsCompatibleFurniture(const FurnitureDetails* a_details) const
    {
        if (!a_details)
            return !RequiresFurniture();
        return IsCompatibleFurniture(a_details->GetTypes().get());
    }

    bool Scene::IsCompatibleFurniture(FurnitureType a_furniture) const
    {
        if (a_furniture.IsNone()) {
            return !RequiresFurniture();
        } else if (a_furniture.IsBed() && allowBed) {
            return true;
        }
        return GetFurnitureTypes().any(a_furniture.value);
    }

    bool Scene::Legacy_IsCompatibleSexCount(int32_t a_males, int32_t a_females) const
    {
        if (a_males < 0 && a_females < 0) {
            return true;
        }

        bool ret = false;
        tags.ForEachExtra([&](const std::string_view a_tag) {
            if (a_tag.find_first_not_of("MFC") != std::string_view::npos) {
                return false;
            }
            if (a_males == -1 || std::count(a_tag.begin(), a_tag.end(), 'M') == a_males) {
                if (a_females == -1 || std::count(a_tag.begin(), a_tag.end(), 'F') == a_females) {
                    ret = true;
                    return true;
                }
            }
            return false;
        });
        return ret;
    }

    bool Scene::Legacy_IsCompatibleSexCountCrt(int32_t a_males, int32_t a_females) const
    {
        if (a_males < 0 || a_females < 0 || a_males > ActorFragment::MAX_ACTOR_COUNT ||
            a_females > ActorFragment::MAX_ACTOR_COUNT - a_males)
            return false;
        enum
        {
            Male = 0,
            Female = 1,
            Either = 2,
        };

        bool ret = false;
        tags.ForEachExtra([&](const std::string_view a_tag) {
            if (a_tag.find_first_not_of("MFC") != std::string_view::npos) {
                return false;
            }
            const auto crt_total = std::count(a_tag.begin(), a_tag.end(), 'C');
            if (crt_total != a_males + a_females) {
                return false;
            }

            int count[3]{};
            for (auto&& position : positions) {
                if (position.data.IsHuman())
                    continue;
                if (position.data.IsNotSex(Sex::Female)) {
                    count[Male]++;
                } else if (position.data.IsNotSex(Sex::Male)) {
                    count[Female]++;
                } else {
                    count[Either]++;
                }
            }
            if (count[Male] <= a_males && count[Male] + count[Either] >= a_males) {
                count[Either] -= a_males - count[Male];
                ret = count[Female] + count[Either] == a_females;
            }
            return ret;
        });
        return ret;
    }


    bool Scene::HasCompatibleAssignment(const std::vector<ActorFragment>& a_fragments) const
    {
        const auto count = a_fragments.size();
        if (count != positions.size() || count > ActorFragment::MAX_ACTOR_COUNT)
            return false;

        std::array<size_t, ActorFragment::MAX_ACTOR_COUNT> compatible{};
        for (size_t actor = 0; actor < count; ++actor) {
            for (size_t position = 0; position < count; ++position) {
                if (positions[position].data.GetCompatibilityScore(a_fragments[actor]) != 0)
                    compatible[actor] |= size_t{ 1 } << position;
            }
            if (compatible[actor] == 0)
                return false;
        }

        // Reachability over at most 32 subsets; no assignment allocation or sorting.
        return Util::HasPerfectAssignment(compatible, count);
    }

    std::vector<std::vector<RE::Actor*>> Scene::FindAssignments(const std::vector<ActorFragment>& a_fragments) const
    {
        if (a_fragments.size() != positions.size())
            return {};

        const auto N = a_fragments.size();
        std::vector fragmentGraph(N, std::vector<std::pair<size_t, int32_t>>{});  // fragment[i] = { { positionIdx, score }, ... }
        for (size_t i = 0; i < N; i++) {
            const auto& fragment = a_fragments[i];
            for (size_t j = 0; j < N; j++) {
                const auto& position = positions[j];
                const auto score = position.data.GetCompatibilityScore(fragment);
                if (score != 0) {
                    fragmentGraph[i].emplace_back(j, score);
                }
            }
        }

        using Assignment = std::vector<std::pair<ActorFragment, size_t>>;
        struct ScoredAssignment
        {
            Assignment assignment{};
            int64_t score{ 0 };

            bool operator<(const ScoredAssignment& other) const { return score > other.score; }
        };
        std::vector<ScoredAssignment> assignments{};
        std::vector<bool> used(N, false);
        Assignment current;
        const std::function<void(size_t, int64_t)> helper = [&](size_t fragmentIdx, int64_t accScore) {
            if (fragmentIdx == N) {
                assignments.emplace_back(current, accScore);
                return;
            }
            for (auto&& [positionIdx, score] : fragmentGraph[fragmentIdx]) {
                if (used[positionIdx]) {
                    continue;
                }
                used[positionIdx] = true;
                current.emplace_back(a_fragments[fragmentIdx], positionIdx);
                helper(fragmentIdx + 1, accScore + score);
                current.pop_back();
                used[positionIdx] = false;
            }
        };
        helper(0, 0);
        if (assignments.empty()) {
            return {};
        }
        std::sort(assignments.begin(), assignments.end());

#ifdef DEBUG
        logger::info("Scene: {} | Found {} assignments", id, assignments.size());
        for (auto&& assignment : assignments) {
            std::string str{};
            str.reserve(assignment.assignment.size() * 2);
            for (auto&& [fragment, positionIdx] : assignment.assignment) {
                str += std::format("{} ", positionIdx);
            }
            logger::info("Assignment: {} | Score: {}", str, assignment.score);
        }
#endif

        std::vector<std::vector<RE::Actor*>> ret{};
        ret.reserve(assignments.size());
        for (auto&& assignment : assignments) {
            std::vector<RE::Actor*> actors(N, nullptr);
            for (auto&& [fragment, positionIdx] : assignment.assignment) {
                actors[positionIdx] = fragment.GetActor();
            }
            ret.push_back(actors);
        }
        return ret;
    }

    size_t Scene::GetNumAdjacentStages(const Stage* a_stage) const
    {
        const auto where = graph.find(a_stage);
        if (where == graph.end())
            return 0;

        return where->second.size();
    }

    const Stage* Scene::GetNthAdjacentStage(const Stage* a_stage, size_t n) const
    {
        const auto where = graph.find(a_stage);
        if (where == graph.end())
            return 0;

        if (n < 0 || n >= where->second.size())
            return 0;

        return where->second[n];
    }

    const std::vector<const Stage*>* Scene::GetAdjacentStages(const Stage* a_stage) const
    {
        const auto where = graph.find(a_stage);
        return where != graph.end() ? &where->second : nullptr;
    }

    RE::BSFixedString Scene::GetNthAnimationEvent(const Stage* a_stage, size_t n) const
    {
        std::string ret{ hash };
        return ret + a_stage->positions[n].event.data();
    }

    std::vector<RE::BSFixedString> Scene::GetAnimationEvents(const Stage* a_stage) const
    {
        std::vector<RE::BSFixedString> events;
        events.reserve(a_stage->positions.size());
        for (const auto& position : a_stage->positions)
            events.emplace_back(std::format("{}{}", hash, position.event));
        return events;
    }

    size_t Scene::GetNumStages() const
    {
        return stages.size();
    }

    const std::vector<const Stage*> Scene::GetAllStages() const
    {
        std::vector<const Stage*> ret{};
        ret.reserve(stages.size());
        for (auto&& stage : stages) {
            ret.push_back(stage.get());
        }
        return ret;
    }

    Scene::NodeType Scene::GetStageNodeType(const Stage* a_stage) const
    {
        if (a_stage == start_animation)
            return NodeType::Root;

        const auto where = graph.find(a_stage);
        if (where == graph.end())
            return NodeType::None;

        return where->second.size() == 0 ? NodeType::Sink : NodeType::Default;
    }

    std::vector<const Stage*> Scene::GetLongestPath(const Stage* a_src) const
    {
        if (!a_src || !graph.contains(a_src))
            return {};
        if (GetStageNodeType(a_src) == NodeType::Sink)
            return { a_src };

        // Find the reachable graph and topological order without recursion or
        // per-node path copies. Parallel edges are counted and removed equally.
        std::vector<const Stage*> reachable{ a_src };
        std::map<const Stage*, size_t> indegree{ { a_src, 0 } };
        for (size_t i = 0; i < reachable.size(); ++i) {
            for (const auto* next : graph.at(reachable[i])) {
                auto [entry, inserted] = indegree.try_emplace(next, 0);
                if (inserted)
                    reachable.push_back(next);
                ++entry->second;
            }
        }
        std::queue<const Stage*> ready;
        for (const auto* node : reachable)
            if (!indegree.at(node))
                ready.push(node);
        std::vector<const Stage*> order;
        while (!ready.empty()) {
            const auto* node = ready.front();
            ready.pop();
            order.push_back(node);
            for (const auto* next : graph.at(node))
                if (--indegree.at(next) == 0)
                    ready.push(next);
        }
        if (order.size() == reachable.size()) {
            struct Route
            {
                size_t length{ 1 };
                const Stage* next{ nullptr };
            };
            std::map<const Stage*, Route> routes;
            for (auto node = order.rbegin(); node != order.rend(); ++node) {
                Route best;
                for (const auto* next : graph.at(*node)) {
                    const auto length = routes.at(next).length + 1;
                    if (length > best.length)
                        best = { length, next };
                }
                routes.emplace(*node, best);
            }
            std::vector<const Stage*> path;
            path.reserve(routes.at(a_src).length);
            for (auto* node = a_src; node; node = routes.at(node).next) path.push_back(node);
            return path;
        }

        constexpr size_t searchBudget = 100000;
        size_t remaining = searchBudget;
        bool exhausted = false;
        std::set<const Stage*> visited{ a_src };
        std::vector<const Stage*> current{ a_src }, best{ a_src };
        // An explicit traversal stack avoids recursive path copies. Every edge
        // examined consumes budget, including edges back into the current path.
        std::vector<size_t> nextEdge{ 0 };
        while (!current.empty()) {
            const auto& edges = graph.at(current.back());
            if (nextEdge.back() == edges.size()) {
                visited.erase(current.back());
                current.pop_back();
                nextEdge.pop_back();
                continue;
            }
            if (!remaining) {
                exhausted = true;
                break;
            }
            --remaining;
            const auto* next = edges[nextEdge.back()++];
            if (visited.contains(next))
                continue;
            visited.insert(next);
            current.push_back(next);
            nextEdge.push_back(0);
            if (current.size() > best.size())
                best = current;
        }
        if (exhausted)
            logger::warn("Cyclic longest-path search exhausted {} edge visits; returning best discovered simple path", searchBudget);
        return best;
    }

    std::vector<const Stage*> Scene::GetShortestPath(const Stage* a_src) const
    {
        if (!a_src || !graph.contains(a_src))
            return {};
        if (GetStageNodeType(a_src) == NodeType::Sink)
            return { a_src };

        std::function<std::vector<const Stage*>(const Stage*)> BFS = [&](const Stage* src) -> std::vector<const Stage*> {
            std::set<const Stage*> visited{ src };
            std::map<const Stage*, const Stage*> pred{ { src, nullptr } };
            std::queue<const Stage*> queue{ { src } };
            while (!queue.empty()) {
                const auto it = queue.front();
                const auto neighbours = graph.find(it);
                assert(neighbours != this->graph.end());
                for (auto&& n : neighbours->second) {
                    if (visited.contains(n))
                        continue;
                    if (GetStageNodeType(n) == NodeType::Sink) {
                        std::vector<const Stage*> ret{ n };
                        auto p = it;
                        while (p != nullptr) {
                            ret.push_back(p);
                            p = pred.at(p);
                        }
                        return { ret.rbegin(), ret.rend() };
                    }
                    pred.emplace(n, it);
                    visited.insert(n);
                    queue.push(n);
                }
                queue.pop();
            }
            return { src };
        };
        return BFS(a_src);
    }

    void Scene::ForEachStage(std::function<bool(Stage*)> a_visitor)
    {
        for (auto&& stage : stages) {
            if (a_visitor(stage.get())) {
                return;
            }
        }
    }

    std::vector<const Stage*> Scene::GetEndingStages() const
    {
        std::vector<const Stage*> ret{};
        for (auto&& [vert, edges] : graph) {
            if (edges.empty()) {
                ret.push_back(vert);
            }
        }
        return ret;
    }

    std::vector<const Stage*> Scene::GetClimaxStages() const
    {
        std::vector<const Stage*> ret{};
        for (auto&& stage : stages) {
            for (auto&& position : stage->positions) {
                if (position.climax) {
                    ret.push_back(stage.get());
                    break;
                }
            }
        }
        return ret;
    }

    std::vector<const Stage*> Scene::GetFixedLengthStages() const
    {
        std::vector<const Stage*> ret{};
        for (auto&& stage : stages) {
            if (stage->fixedlength)
                ret.push_back(stage.get());
        }
        return ret;
    }

}  // namespace Registry
