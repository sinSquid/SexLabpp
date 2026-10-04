#pragma once

#include <functional>

// Simple cached single thread consumer. Intended to provide cheap async operations
// without having to manage a platform thread manually. Cached threads are disposed of
// after 2 seconds of non-operation. Orderly destruction drains accepted tasks.
namespace Util::AsyncIO
{
    void Submit(std::move_only_function<void()> a_task);
}
