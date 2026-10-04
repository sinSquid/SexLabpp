#pragma once
#include <atomic>
#include <memory>

namespace Util
{
    // Copies share only the acknowledgement for this particular edit. A later
    // edit gets a new receipt, so an older save cannot acknowledge newer data.
    class DirtyFlag
    {
      public:
        DirtyFlag(bool dirty = false) : receipt(std::make_shared<std::atomic_bool>(!dirty)) {}
        DirtyFlag& operator=(bool dirty)
        {
            receipt = std::make_shared<std::atomic_bool>(!dirty);
            return *this;
        }
        operator bool() const { return !receipt->load(); }
        std::shared_ptr<std::atomic_bool> Receipt() const { return receipt; }

      private:
        std::shared_ptr<std::atomic_bool> receipt;
    };
}
