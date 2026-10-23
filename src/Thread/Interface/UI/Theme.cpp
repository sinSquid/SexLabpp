#include "Theme.h"

#include "Util/AsyncIO.h"
#include "Util/AtomicWrite.h"

#include <optional>

namespace Thread::Interface::UI::Theme
{
    namespace
    {
        template<class T>
        void VisitNumbers(T& object, const auto& visit)
        {
            glz::for_each_field(object, [&](auto& field) {
                using Field = std::remove_cvref_t<decltype(field)>;
                if constexpr (std::is_same_v<Field, float>) visit(field);
                else if constexpr (glz::reflectable<Field>) VisitNumbers(field, visit);
            });
        }
        constexpr auto THEME_PATH = USER_CONFIGS("ui_theme.json");

        struct WriteOptions : glz::opts
        {
            bool prettify = true;
            std::uint8_t indentation_width = 2;
        };

        bool loadComplete{ false };
    }

    void Sanitize(Data& values)
    {
        static const auto defaults = [] {
            Data initial;
            std::vector<float> result;
            VisitNumbers(initial, [&](float value) { result.push_back(value); });
            return result;
        }();
        size_t index = 0;
        VisitNumbers(values, [&](float& value) {
            if (!std::isfinite(value) || value < 0.0f) value = defaults[index];
            ++index;
        });
        const Data initial;
        // Font sizes and these scale/divisor fields must be strictly positive.
        auto fontDefaults = initial.fontSize;
        std::vector<float> fonts;
        VisitNumbers(fontDefaults, [&](float value) { fonts.push_back(value); });
        index = 0;
        VisitNumbers(values.fontSize, [&](float& value) {
            if (value <= 0.0f) value = fonts[index];
            ++index;
        });
        if (values.offset.dragDistance <= 0.0f) values.offset.dragDistance = initial.offset.dragDistance;
        if (values.geometry.nestedMenuScale <= 0.0f) values.geometry.nestedMenuScale = initial.geometry.nestedMenuScale;
    }

    void Load()
    {
        loadComplete = false;
        Util::AsyncIO::Submit([]() {
            std::optional<Data> loadedTheme;
            std::error_code fileError;
            if (fs::exists(THEME_PATH, fileError)) {
                Data candidate{};
                std::string buffer;
                if (const auto error = glz::read_file_json(candidate, THEME_PATH, buffer); error) {
                    logger::error("Unable to load UI theme: {}", glz::format_error(error, buffer));
                } else {
                    Sanitize(candidate);
                    loadedTheme = candidate;
                    logger::info("Loaded UI theme from {}", THEME_PATH);
                }
            } else if (fileError) {
                logger::error("Unable to inspect UI theme path {}: {}", THEME_PATH, fileError.message());
            } else {
                loadedTheme.emplace();
                logger::info("UI theme file not found; using defaults");
            }

            SKSE::GetTaskInterface()->AddTask([loadedTheme = std::move(loadedTheme)]() mutable {
                if (loadedTheme)
                    data = std::move(*loadedTheme);
                loadComplete = true;
            });
        });
    }

    void Save()
    {
        if (!IsLoaded()) {
            logger::warn("UI theme save ignored while the initial load is pending");
            return;
        }

        auto snapshot = data;
        Util::AsyncIO::Submit([snapshot = std::move(snapshot)]() {
            const fs::path path{ THEME_PATH };
            std::error_code directoryError;
            fs::create_directories(path.parent_path(), directoryError);
            if (directoryError) {
                logger::error("Unable to create UI theme directory {}: {}", path.parent_path().string(), directoryError.message());
                return;
            }

            std::string buffer;
            if (const auto error = glz::write<WriteOptions{}>(snapshot, buffer); error) {
                logger::error("Unable to serialize UI theme: {}", glz::format_error(error, buffer));
                return;
            }

            try {
                Util::AtomicWrite(path, buffer);
            } catch (const std::exception& error) {
                logger::error("Unable to write UI theme to {}: {}", THEME_PATH, error.what());
                return;
            }
            logger::info("Saved UI theme to {}", THEME_PATH);
        });
    }

    bool IsLoaded()
    {
        return loadComplete;
    }
}
