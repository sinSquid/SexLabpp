#include "NiMath.h"

namespace Thread::NiNode::NiMath
{
    namespace
    {
        inline RE::NiPoint3 ProjectToXY(const RE::NiPoint3& v)
        {
            return { v.x, v.y, 0.0f };
        }

        inline RE::NiPoint3 ProjectToXZ(const RE::NiPoint3& v)
        {
            return { v.x, 0.0f, v.z };
        }

        inline RE::NiPoint3 ProjectToYZ(const RE::NiPoint3& v)
        {
            return { 0.0f, v.y, v.z };
        }
    }

    Segment Segment::ShortestSegmentTo(const Segment& other) const
    {
        if (IsPoint() && other.IsPoint()) {
            return Segment{ first, other.first };
        }
        const auto vSelf = Vector();
        const auto vOther = other.Vector();
        const auto vFirst = other.first - first;

        const auto lenSelf = vSelf.SqrLength();
        const auto lenOther = vOther.SqrLength();

        const auto dotSelfFirst = vSelf.Dot(vFirst);
        const auto dotOtherFirst = vOther.Dot(vFirst);

        float tSelf, tOther;
        if (IsPoint()) {
            tSelf = 0.0f;
            tOther = std::clamp(-dotOtherFirst / lenOther, 0.0f, 1.0f);
        } else if (other.IsPoint()) {
            tSelf = std::clamp(dotSelfFirst / lenSelf, 0.0f, 1.0f);
            tOther = 0.0f;
        } else {
            const auto dotSelfOther = vSelf.Dot(vOther);
            const auto det = lenSelf * lenOther - dotSelfOther * dotSelfOther;

            tSelf = det <= FLT_EPSILON * lenSelf * lenOther ? 0.0f :
                                                              std::clamp((dotSelfFirst * lenOther - dotOtherFirst * dotSelfOther) / det, 0.0f, 1.0f);
            tOther = (tSelf * dotSelfOther - dotOtherFirst) / lenOther;
            if (tOther < 0.0f) {
                tOther = 0.0f;
                tSelf = std::clamp(dotSelfFirst / lenSelf, 0.0f, 1.0f);
            } else if (tOther > 1.0f) {
                tOther = 1.0f;
                tSelf = std::clamp((dotSelfFirst + dotSelfOther) / lenSelf, 0.0f, 1.0f);
            }
        }

        const auto c1 = first + (vSelf * tSelf);
        const auto c2 = other.first + (vOther * tOther);
        return Segment{ c1, c2 };
    }

    bool Segment::IsBetween(const Segment& u, const Segment& v) const
    {
        auto s = Vector();
        auto uVec = u.Vector();
        auto vVec = v.Vector();

        if (s.SqrLength() < FLT_EPSILON || uVec.SqrLength() < FLT_EPSILON || vVec.SqrLength() < FLT_EPSILON)
            return false;

        s.Unitize();
        uVec.Unitize();
        vVec.Unitize();

        const auto n = uVec.Cross(vVec);
        if (n.SqrLength() < FLT_EPSILON)
            return false;

        float sideU = n.Dot(uVec.Cross(s));
        float sideV = n.Dot(s.Cross(vVec));
        return sideU >= -FLT_EPSILON && sideV >= -FLT_EPSILON;
    }


    Segment BestFit(std::span<const RE::NiPoint3> a_points)
    {
        switch (a_points.size()) {
        case 0:
            return { RE::NiPoint3::Zero(), RE::NiPoint3::Zero() };
        case 1:
            return { a_points[0], a_points[0] };
        case 2:
            return { a_points[0], a_points[1] };
        }

        // 1) Centroid
        RE::NiPoint3 centroid{};
        for (const auto& p : a_points) {
            centroid += p;
        }
        centroid /= static_cast<float>(a_points.size());

        // 2) Covariance matrix
        RE::NiMatrix3 cov{
            { 0.0f, 0.0f, 0.0f },
            { 0.0f, 0.0f, 0.0f },
            { 0.0f, 0.0f, 0.0f },
        };
        for (const auto& p : a_points) {
            RE::NiPoint3 d = p - centroid;
            for (size_t i = 0; i < 3; ++i) {
                for (size_t j = 0; j < 3; ++j) {
                    cov.entry[i][j] += d[i] * d[j];
                }
            }
        }
        // Scaling does not change eigenvectors. Normalize by the largest
        // diagonal to keep tiny but nonzero trajectories numerically useful.
        const float scale = std::max({ cov.entry[0][0], cov.entry[1][1], cov.entry[2][2] });
        if (scale <= 0.0f)
            return { centroid, centroid };
        cov = cov * (1.0f / scale);

        constexpr int PCA_MAX_ITERATIONS = 50;
        constexpr float PCA_DIRECTION_TOLERANCE_SQR = 1e-6f;
        constexpr float PCA_MIN_VECTOR_NORM_SQR = 1e-12f;
        RE::NiPoint3 dir{ 1.0f, 0.0f, 0.0f };
        float bestVariance = -1.0f;
        // A single seed may be orthogonal to the principal eigenspace. At
        // least one of these three independent seeds has a component in it.
        for (size_t seed = 0; seed < 3; ++seed) {
            RE::NiPoint3 candidate{ 0.0f, 0.0f, 0.0f };
            candidate[seed] = 1.0f;
            for (int i = 0; i < PCA_MAX_ITERATIONS; ++i) {
                auto next = cov * candidate;
                if (next.SqrLength() < PCA_MIN_VECTOR_NORM_SQR)
                    break;
                next.Unitize();
                const auto diff = next - candidate;
                candidate = next;
                if (diff.SqrLength() < PCA_DIRECTION_TOLERANCE_SQR)
                    break;
            }
            const auto variance = candidate.Dot(cov * candidate);
            if (variance > bestVariance) {
                bestVariance = variance;
                dir = candidate;
            }
        }

        // 4) Find line extents
        float minT = FLT_MAX;
        float maxT = -FLT_MAX;
        for (const auto& p : a_points) {
            float t = (p - centroid).Dot(dir);
            minT = std::min(minT, t);
            maxT = std::max(maxT, t);
        }

        const auto start = centroid + dir * minT;
        const auto end = centroid + dir * maxT;
        return { start, end };
    }

    RE::NiMatrix3 RotateTowards(const RE::NiPoint3& v, const RE::NiPoint3& i, float maxRadians)
    {
        const RE::NiMatrix3 identity{ { 1, 0, 0 }, { 0, 1, 0 }, { 0, 0, 1 } };
        if (v.SqrLength() == 0.0f || i.SqrLength() == 0.0f)
            return identity;
        auto from = v, to = i;
        from.Unitize();
        to.Unitize();
        RE::NiPoint3 axis = from.Cross(to);
        const float sin_theta = axis.Length();
        const float cos_theta = std::clamp(from.Dot(to), -1.0f, 1.0f);
        if (sin_theta < FLT_EPSILON) {
            if (cos_theta >= 0.0f)
                return identity;
            axis = from.Cross(RE::NiPoint3{ 1, 0, 0 });
            if (axis.SqrLength() < 1e-6f)
                axis = from.Cross(RE::NiPoint3{ 0, 1, 0 });
            axis.Unitize();
        } else {
            axis /= sin_theta;
        }
        const float theta = std::atan2(sin_theta, cos_theta);
        const float step = maxRadians != 0.0f ? std::clamp(maxRadians, 0.0f, theta) : theta;

        RE::NiMatrix3 K{
            { 0, -axis.z, axis.y },
            { axis.z, 0, -axis.x },
            { -axis.y, axis.x, 0 }
        };

        return identity + K * std::sin(step) + (K * K) * (1.0f - std::cos(step));
    }

    float GetAngle(const RE::NiPoint3& v1, const RE::NiPoint3& v2)
    {
        return std::acos(GetAngleCos(v1, v2));
    }

    float GetAngleCos(const RE::NiPoint3& v1, const RE::NiPoint3& v2)
    {
        const auto dot = v1.Dot(v2);
        const auto l = v1.Length() * v2.Length();
        return l > 0.0f ? std::clamp(dot / l, -1.0f, 1.0f) : 1.0f;
    }

    float GetAngleDegree(const RE::NiPoint3& v1, const RE::NiPoint3& v2)
    {
        return RE::rad_to_deg(GetAngle(v1, v2));
    }

    void EnsureParallelDirection(RE::NiPoint3& v, const RE::NiPoint3& reference)
    {
        if (v.Dot(reference) < 0.0f) {
            v = -v;
        }
    }

    void EnsureAntiParallelDirection(RE::NiPoint3& v, const RE::NiPoint3& reference)
    {
        if (v.Dot(reference) > 0.0f) {
            v = -v;
        }
    }

    float GetAngleXY(const RE::NiMatrix3& rot)
    {
        return std::atan2(rot.entry[0][1], rot.entry[0][0]);
    }

    float GetAngleXZ(const RE::NiMatrix3& rot)
    {
        return std::atan2(-rot.entry[0][2], rot.entry[0][0]);
    }

    float GetAngleYZ(const RE::NiMatrix3& rot)
    {
        return std::atan2(-rot.entry[1][2], rot.entry[1][1]);
    }

    float GetAngleXZ(const RE::NiPoint3& u, const RE::NiPoint3& v)
    {
        return GetAngle(ProjectToXZ(u), ProjectToXZ(v));
    }

    float GetAngleXY(const RE::NiPoint3& u, const RE::NiPoint3& v)
    {
        return GetAngle(ProjectToXY(u), ProjectToXY(v));
    }

    float GetAngleYZ(const RE::NiPoint3& u, const RE::NiPoint3& v)
    {
        return GetAngle(ProjectToYZ(u), ProjectToYZ(v));
    }

    RE::NiPoint3 ProjectedComponent(RE::NiPoint3 U, RE::NiPoint3 V)
    {
        const auto lengthSquared = V.SqrLength();
        return lengthSquared != 0.0f ? V * (U.Dot(V) / lengthSquared) : RE::NiPoint3::Zero();
    }

    RE::NiPoint3 OrthogonalComponent(RE::NiPoint3 U, RE::NiPoint3 V)
    {
        return U - ProjectedComponent(U, V);
    }

}  // namespace Thread::NiNode::NiMath
