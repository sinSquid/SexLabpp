#include "NiMotion.h"

namespace Thread::NiNode
{
    NiMotion::NiMotion(size_t capacity, size_t minMoments) :
      _capacity(std::max(capacity, size_t{ 1 })), _minMoments(minMoments)
    {
        for (auto& moment : _moments) {
            moment.resize(_capacity);
        }
        _headBounds.resize(_capacity);
        _timestamps.resize(_capacity);
        _present.resize(_capacity);
    }

    void NiMotion::Push(const Node::NodeData& nodes, float timeStamp)
    {
        for (auto& entry : descriptorCache)
            entry.reset();
        const size_t idx = _writeIndex;
        _present[idx].reset();
        const auto store = [&](Anchor anchor, const RE::NiPoint3& value) {
            if (std::isfinite(timeStamp) && std::isfinite(value.x) && std::isfinite(value.y) && std::isfinite(value.z)) {
                _moments[anchor][idx] = value;
                _present[idx].set(static_cast<size_t>(anchor));
            }
        };
        for (auto& moment : _moments)
            moment[idx] = RE::NiPoint3::Zero();
        _headBounds[idx] = ObjectBound{};
        _timestamps[idx] = timeStamp;

        if (const auto niHead = nodes.head) {
            store(Anchor::vHeadX, niHead->world.rotate.GetVectorX());
            store(Anchor::vHeadY, niHead->world.rotate.GetVectorY());
            store(Anchor::vHeadZ, niHead->world.rotate.GetVectorZ());
            store(Anchor::pHead, nodes.head->world.translate);
            if (auto opt = ObjectBound::MakeBoundingBox(niHead.get())) {
                _headBounds[idx] = *opt;
                const auto down = _headBounds[idx].boundMin.z * 0.17f;
                const auto forward = _headBounds[idx].boundMax.y * 0.88f;
                if (_present[idx].test(Anchor::vHeadZ) && _present[idx].test(Anchor::pHead))
                    store(Anchor::pThroat, (_moments[Anchor::vHeadZ][idx] * down) + _moments[Anchor::pHead][idx]);
                if (_present[idx].test(Anchor::vHeadY) && _present[idx].test(Anchor::pThroat))
                    store(Anchor::pMouth, (_moments[Anchor::vHeadY][idx] * forward) + _moments[Anchor::pThroat][idx]);
            } else {
                _headBounds[idx] = ObjectBound{};
                logger::warn("Failed to get head bounding box");
            }
        }

        if (!nodes.schlongs.empty()) {
            const auto sSchlong = nodes.schlongs.front()->GetReferenceSegment();
            store(Anchor::pSchlongBase, sSchlong.first);
            store(Anchor::pSchlongTip, sSchlong.second);
        }

        if (const auto sVaginal = nodes.GetVaginalSegment()) {
            store(Anchor::pVaginalStart, sVaginal->first);
            store(Anchor::pVaginalEnd, sVaginal->second);
        }
        if (const auto& niClitoris = nodes.clitoris) {
            store(Anchor::pClitoris, niClitoris->world.translate);
        }

        if (const auto sAnal = nodes.GetAnalSegment()) {
            store(Anchor::pAnalStart, sAnal->first);
            store(Anchor::pAnalEnd, sAnal->second);
        }

        const auto sCrotch = nodes.GetCrotchSegment();
        store(Anchor::pSpineLower, sCrotch.first);
        store(Anchor::pPelvis, sCrotch.second);

        _writeIndex = (_writeIndex + 1) % _capacity;
        _size = std::min(_size + 1, _capacity);
    }

    void NiMotion::ForEachMoment(Anchor c, const std::function<bool(const RE::NiPoint3&, float)>& func) const
    {
        for (size_t i = ValidStart(c); i < _size; i++) {
            if (func(GetNthMoment(c, i), GetNthTimestamp(i))) {
                break;
            }
        }
    }

    NiMath::Segment NiMotion::GetMotion(Anchor c) const
    {
        const auto start = ValidStart(c);
        const auto count = _size - start;
        if (count < 2) {
            return NiMath::Segment(count == 1 ? GetNthMoment(c, start) : RE::NiPoint3::Zero());
        }
        if (count == 2)
            return NiMath::Segment(GetNthMoment(c, start), GetNthMoment(c, start + 1));
        // PCA is order independent; a fully valid window occupies the first _size slots.
        if (start == 0)
            return NiMath::BestFit(std::span<const RE::NiPoint3>{ _moments[c].data(), _size });
        std::vector<RE::NiPoint3> valid;
        valid.reserve(count);
        for (size_t i = start; i < _size; ++i)
            valid.push_back(GetNthMoment(c, i));
        return NiMath::BestFit(std::span<const RE::NiPoint3>{ valid.data(), valid.size() });
    }

    MotionDescriptor NiMotion::DescribeMotion(Anchor c) const
    {
        auto& cached = descriptorCache.at(static_cast<size_t>(c));
        if (!cached)
            cached = ComputeDescriptor(c);
        return *cached;
    }

    MotionDescriptor NiMotion::ComputeDescriptor(Anchor c) const
    {
        MotionDescriptor out{ GetMotion(c) };

        const auto start = ValidStart(c);
        const auto count = _size - start;
        if (count < _minMoments || count < 2) {
            return out;
        }

        out.duration = GetNthTimestamp(_size - 1) - GetNthTimestamp(start);
        auto axis = out.trajectory.Vector();
        axis.Unitize();
        const auto mean = out.Mean();

        // Initialize accumulators
        float totalDist = 0.0f;
        float peakSpeed = 0.0f;
        float posVar = 0.0f;
        float impulse = 0.0f;
        float prevProj = 0.0f;
        int signChanges = 0;

        RE::NiPoint3 avgDir{};
        std::vector<RE::NiPoint3> dirs;
        dirs.reserve(count - 1);

        // Cached values for pairwise/triple calculations
        const RE::NiPoint3 *p0 = nullptr, *p1 = nullptr;
        float t0 = 0.0f, t1 = 0.0f;

        ForEachMoment(c, [&](const RE::NiPoint3& p, float t) {
            // Positional variance (scatter around trajectory)
            const RE::NiPoint3 rel = p - mean;
            const float proj = rel.Dot(axis);
            const RE::NiPoint3 closest = mean + axis * proj;
            posVar += p.GetDistance(closest);

            // Oscillation (sign changes along trajectory axis)
            if (p1 != nullptr && (proj * prevProj < 0.0f))
                signChanges++;
            prevProj = proj;

            // Dependent calculations
            if (p1 != nullptr) {
                const float dt1 = t - t1;
                if (dt1 > 0.0f) {
                    // Path length & speed
                    const float d = p.GetDistance(*p1);
                    totalDist += d;
                    peakSpeed = std::max(peakSpeed, d / dt1);

                    // Directional variance
                    RE::NiPoint3 dir = p - *p1;
                    if (dir.Length() > FLT_EPSILON) {
                        dir.Unitize();
                        avgDir += dir;
                        dirs.push_back(dir);
                    }

                    // Impulse
                    if (p0 != nullptr) {
                        const float dt0 = t1 - t0;
                        if (dt0 > 0.0f) {
                            const RE::NiPoint3 v0 = (*p1 - *p0) / dt0;
                            const RE::NiPoint3 v1 = (p - *p1) / dt1;
                            impulse = std::max(impulse, (v1 - v0).Length());
                        }
                    }
                }
            }

            p0 = p1;
            p1 = &p;
            t0 = t1;
            t1 = t;

            return false;
        });

        // Finalize calculations
        out.totalDistance = totalDist;
        out.avgSpeed = out.duration > 0.0f ? totalDist / out.duration : 0.0f;
        out.peakSpeed = peakSpeed;
        out.positionalVariance = posVar / static_cast<float>(count);
        out.oscillation = static_cast<float>(signChanges) / static_cast<float>(count - 1);
        out.impulse = impulse;

        // Directional variance
        float dirVar = 0.0f;
        if (!dirs.empty()) {
            avgDir.Unitize();
            for (const auto& d : dirs) {
                dirVar += 1.0f - std::abs(d.Dot(avgDir));
            }
            dirVar /= static_cast<float>(dirs.size());
        }
        out.directionalVariance = dirVar;

        return out;
    }

    size_t NiMotion::ValidStart(Anchor c) const
    {
        size_t start = _size;
        while (start > 0 && _present[AbsoluteToRelativeIndex(start - 1)].test(static_cast<size_t>(c)))
            --start;
        return start;
    }

    size_t NiMotion::AbsoluteToRelativeIndex(size_t n) const
    {
        assert(n < _size);
        // If buffer is not full, physical index equals logical index
        // If buffer is full, account for the ring buffer wraparound
        return (_size < _capacity) ? n : ((_writeIndex + n) % _capacity);
    }

    const RE::NiPoint3& NiMotion::GetNthMoment(Anchor c, size_t n) const
    {
        assert(c < NUM_ANCHORS);
        assert(n < _size);
        return _moments[c][AbsoluteToRelativeIndex(n)];
    }

    const ObjectBound& NiMotion::GetNthHeadBound(size_t n) const
    {
        assert(n < _size);
        return _headBounds[AbsoluteToRelativeIndex(n)];
    }

    float NiMotion::GetNthTimestamp(size_t n) const
    {
        assert(n < _size);
        return _timestamps[AbsoluteToRelativeIndex(n)];
    }

}  // namespace Thread::NiNode
