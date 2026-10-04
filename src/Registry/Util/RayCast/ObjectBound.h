#pragma once

#include <glm/glm.hpp>
#include <optional>

struct ObjectBound
{
    static RE::NiPointer<RE::NiCollisionObject> GetCollisionNodeRecurse(RE::NiNode* a_node, size_t a_recurse);
    static std::optional<ObjectBound> MakeBoundingBox(RE::NiNode* a_niobj);

  public:
    ObjectBound() = default;
    ObjectBound(glm::vec3 pBoundMin, glm::vec3 pBoundMax, glm::vec3 pWorldBoundMin, glm::vec3 pWorldBoundMax, glm::vec3 pRotation) :
      boundMin(pBoundMin), boundMax(pBoundMax), worldBoundMin(pWorldBoundMin), worldBoundMax(pWorldBoundMax), rotation(pRotation) {}
    ~ObjectBound() = default;

  public:
    glm::vec3 GetCenterWorld() const;
    bool IsPointInside(float a_x, float a_y, float a_z) const;
    bool IsPointInside(const glm::vec3& a_point) const;
    bool IsPointInside(const RE::NiPoint3& a_point) const;
    bool IsValid() const;

    glm::vec3 boundMin{ 0.0f };
    glm::vec3 boundMax{ 0.0f };
    glm::vec3 worldBoundMin{ 0.0f };
    glm::vec3 worldBoundMax{ 0.0f };
    glm::vec3 rotation{ 0.0f };
};
