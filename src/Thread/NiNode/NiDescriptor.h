#pragma once

#include <SimpleIni.h>

#include "Util/StringUtil.h"

namespace Thread::NiNode
{
    namespace NiType
    {
        enum class Cluster
        {
            None = 0,
            Crotch,
            Head,
            KissingCl,
        };
        constexpr static inline size_t NUM_CLUSTERS = magic_enum::enum_count<Cluster>();

        enum class Type
        {
            None = 0,
#define NI_TYPE(name, cluster) name,

#include "NiType.def"

#undef NI_TYPE
        };
        constexpr static inline size_t NUM_TYPES = magic_enum::enum_count<Type>();

        inline Cluster GetClusterForType(Type type)
        {
#define NI_TYPE(name, cluster)   \
    if (type == Type::name) {    \
        return Cluster::cluster; \
    }
#include "NiType.def"
#undef NI_TYPE
            return Cluster::None;
        }

        inline std::vector<Type> GetTypesForCluster(Cluster a_cluster)
        {
            std::vector<Type> types;
#define NI_TYPE(name, cluster)           \
    if (a_cluster == Cluster::cluster) { \
        types.push_back(Type::name);     \
    }
#include "NiType.def"
#undef NI_TYPE
            return types;
        }
    }  // namespace NiType

    class INiDescriptor
    {
      public:
        enum class Feature : uint8_t
        {
            Distance01,
            Time01,
            Velocity01,
            Oscillation01,
            Impulse01,
            Stability01,
            StabilityVariance01,

            Distance02,
            Time02,
            Velocity02,
            Oscillation02,
            Impulse02,
            Stability02,
            StabilityVariance02,

            Distance03,
            Time03,
            Velocity03,
            Oscillation03,
            Impulse03,
            Stability03,
            StabilityVariance03,

            Distance04,

            Angle01,
            Angle02,
            Angle03,
        };
        constexpr static inline size_t NUM_FEATURES = magic_enum::enum_count<Feature>();

      public:
        virtual ~INiDescriptor() = default;

        virtual float Predict() const = 0;
        virtual float PredictCluster(const std::vector<const INiDescriptor*>& descriptors) const = 0;
        virtual float GetFeature(Feature feature) const = 0;
        virtual std::string CsvRow() const = 0;
        virtual NiType::Type GetType() const = 0;

      public:
        static std::string CreateCsvHeader(NiType::Cluster cluster)
        {
            std::string header;
            for (const auto type : NiType::GetTypesForCluster(cluster)) {
                const auto name = magic_enum::enum_name(type);
                if (!header.empty())
                    header += ",";
                header += std::format("Id_{},", name);
                for (const auto feature : magic_enum::enum_names<Feature>())
                    header += std::format("{}_{},", name, feature);
                header += std::format("{}_Prediction", name);
            }
            return header;
        }

        static std::string CreateCsvRow(const std::vector<INiDescriptor*>& descriptors, NiType::Cluster cluster)
        {
            std::string row;
            for (const auto type : NiType::GetTypesForCluster(cluster)) {
                if (!row.empty())
                    row += ",";
                const auto found = std::ranges::find(descriptors, type, [](auto* descriptor) { return descriptor->GetType(); });
                if (found != descriptors.end()) {
                    row += (*found)->CsvRow();
                } else {
                    row += std::string(magic_enum::enum_name(type));
                    // Missing descriptors have zero features in both training and runtime.
                    for (size_t i = 0; i < NUM_FEATURES + 1; ++i) row += ",0";
                }
            }
            return row;
        }
    };

    template <NiType::Type Id = NiType::Type::None>
    class NiDescriptor :
      public INiDescriptor
    {
      public:
        void AddValue(Feature feature, float value)
        {
            features[static_cast<size_t>(feature)] = value;
        }

        float Predict() const override
        {
            return std::inner_product(coefficients.begin(), coefficients.end(), features.begin(), bias);
        }

        float GetFeature(Feature feature) const override
        {
            return features[static_cast<size_t>(feature)];
        }

        float PredictCluster(const std::vector<const INiDescriptor*>& descriptors) const override
        {
            if (!clusterModel)
                return Predict();
            float result = bias;
            for (const auto* descriptor : descriptors) {
                const auto& weights = clusterCoefficients[static_cast<size_t>(descriptor->GetType())];
                for (const auto feature : magic_enum::enum_values<Feature>())
                    result += weights[static_cast<size_t>(feature)] * descriptor->GetFeature(feature);
            }
            return result;
        }

        std::string CsvRow() const override
        {
            const auto prediction = Predict();
            std::string row = std::format("{},", magic_enum::enum_name(Id));
            const auto allFeatures = magic_enum::enum_values<Feature>();
            for (const auto& feature : allFeatures) {
                const auto featureValue = features[static_cast<size_t>(feature)];
                row += std::to_string(featureValue) + ",";
            }
            return std::format("{}{}", row, prediction);
        }

        NiType::Type GetType() const override
        {
            return Id;
        }

      public:
        static void Initialize(CSimpleIniA& inifile)
        {
            constexpr auto NaN = std::numeric_limits<float>::quiet_NaN();
            std::string section{ magic_enum::enum_name<NiType::Type>(Id) };
            bias = static_cast<float>(inifile.GetDoubleValue(section.c_str(), "bias", NaN));
            if (std::isnan(bias)) {
                const auto err = std::format("Descriptor '{}': Missing bias value", section);
                throw std::runtime_error(err);
            }
            clusterModel = std::string_view(inifile.GetValue(section.c_str(), "schema", "legacy")) == "cluster-v2";
            for (auto& weights : clusterCoefficients) weights.fill(0.0f);
            if (clusterModel) {
                const auto cluster = NiType::GetClusterForType(Id);
                for (const auto type : NiType::GetTypesForCluster(cluster)) {
                    for (const auto& [feature, name] : magic_enum::enum_entries<Feature>()) {
                        const auto key = Util::CastLower(std::format("{}_{}", magic_enum::enum_name(type), name));
                        const auto value = static_cast<float>(inifile.GetDoubleValue(section.c_str(), key.c_str(), 0.0));
                        if (!std::isfinite(value))
                            throw std::runtime_error("Non-finite cluster coefficient");
                        clusterCoefficients[static_cast<size_t>(type)][static_cast<size_t>(feature)] = value;
                    }
                }
                return;
            }
            const auto features = magic_enum::enum_entries<Feature>();
            for (const auto& [feature, name] : features) {
                const auto lowerName = Util::CastLower(std::string{ name });
                const auto value = static_cast<float>(inifile.GetDoubleValue(section.c_str(), lowerName.c_str(), NaN));
                if (std::isnan(value)) {
                    const auto err = std::format("Descriptor '{}': Missing value for feature '{}'", section, name);
                    throw std::runtime_error(err);
                }
                coefficients[static_cast<size_t>(feature)] = value;
            }
            logger::info("{}: Loaded {} coefficients, bias={:.3f}", section, coefficients, bias);
        }

      private:
        std::array<float, NUM_FEATURES> features{ 0.0f };
        static inline std::array<float, NUM_FEATURES> coefficients{ 0.0f };
        static inline float bias{ 0.0f };
        static inline bool clusterModel{ false };
        static inline std::array<std::array<float, NUM_FEATURES>, NiType::NUM_TYPES> clusterCoefficients{};
    };

}  // namespace Thread::NiNode
