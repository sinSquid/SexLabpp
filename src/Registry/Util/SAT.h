#pragma once

#include "RayCast/ObjectBound.h"
#ifndef GLM_ENABLE_EXPERIMENTAL
#define GLM_ENABLE_EXPERIMENTAL
#endif
#include <array>
#include <glm/gtx/euler_angles.hpp>
#include <limits>
#include <optional>
#include <vector>

namespace SAT
{
    struct OrientedObjectBound
    {
        OrientedObjectBound(RE::NiNode* a_origin, const ObjectBound& a_bound) :
          origin(a_origin), box(a_bound) {}
        OrientedObjectBound(RE::NiNode* a_origin) :
          origin(a_origin), box([&]() {
				const auto ret = ObjectBound::MakeBoundingBox(a_origin);
				return ret ? *ret : ObjectBound{}; }()) {}
        ~OrientedObjectBound() = default;

        std::array<glm::vec3, 8> GetCorners() const
        {
            const auto center = box.GetCenterWorld();
            const auto halfsize = (box.boundMax - box.boundMin) * 0.5f;
            const auto rotate = glm::mat3(glm::eulerAngleXYZ(box.rotation.x, box.rotation.y, box.rotation.z));
            const auto ex = rotate[0] * halfsize.x;
            const auto ey = rotate[1] * halfsize.y;
            const auto ez = rotate[2] * halfsize.z;
            return { center - ex - ey - ez, center + ex - ey - ez,
                center - ex + ey - ez, center + ex + ey - ez,
                center - ex - ey + ez, center + ex - ey + ez,
                center - ex + ey + ez, center + ex + ey + ez };
        }

        RE::NiNode* origin;
        ObjectBound box;
    };

    struct SATResult
    {
        float mtv{ std::numeric_limits<float>::max() };
        glm::vec3 mtv_axis{};
    };

    inline std::vector<glm::vec3> GetAxes(const OrientedObjectBound& a_obb1, const OrientedObjectBound& a_obb2)
    {
        const auto& r1 = a_obb1.box.rotation;
        const auto& r2 = a_obb2.box.rotation;
        const std::array rotations{ glm::mat3(glm::eulerAngleXYZ(r1.x, r1.y, r1.z)),
            glm::mat3(glm::eulerAngleXYZ(r2.x, r2.y, r2.z)) };

        std::vector<glm::vec3> axes;
        axes.reserve(15);
        for (size_t n = 0; n < rotations.size(); n++) {
            for (int i = 0; i < 3; i++) {
                axes.push_back(glm::normalize(rotations[n][i]));
            }
        }
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                glm::vec3 axis = glm::cross(rotations[0][i], rotations[1][j]);
                if (glm::dot(axis, axis) > 1e-12f) {
                    axes.push_back(glm::normalize(axis));
                }
            }
        }
        return axes;
    }

    inline std::optional<SATResult> SAT(const OrientedObjectBound& a_obb1, const OrientedObjectBound& a_obb2)
    {
        if (!a_obb1.box.IsValid() || !a_obb2.box.IsValid())
            return std::nullopt;
        const auto corner1 = a_obb1.GetCorners(), corner2 = a_obb2.GetCorners();
        const auto axes = GetAxes(a_obb1, a_obb2);

        SATResult ret;
        for (auto&& axis : axes) {
            const auto project = [&axis](const std::array<glm::vec3, 8>& points) -> std::pair<float, float> {
                float min = std::numeric_limits<float>::max(), max = std::numeric_limits<float>::lowest();
                for (const auto& point : points) {
                    float projection = glm::dot(axis, point);
                    min = std::min(projection, min);
                    max = std::max(projection, max);
                }
                return { min, max };
            };

            const auto [start1, end1] = project(corner1);
            const auto [start2, end2] = project(corner2);

            if (end1 < start2 || end2 < start1)
                return std::nullopt;
            // Include containment: moving either box out may require more
            // than the width of the interval intersection.
            const auto negative = end1 - start2;
            const auto positive = end2 - start1;
            const auto overlap = std::min(negative, positive);
            if (ret.mtv > overlap) {
                ret.mtv = overlap;
                ret.mtv_axis = negative < positive ? -axis : axis;
            }
        }
        return ret;
    }

}