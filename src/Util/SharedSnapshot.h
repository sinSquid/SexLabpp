#pragma once
#include <memory>
#include <mutex>
#include <utility>

namespace Util
{
    // Copy ownership while holding the slot lock; readers keep the object alive
    // independently of a later reset. Works without atomic<shared_ptr> support.
    template <class T>
    class SharedSnapshot
    {
      public:
        SharedSnapshot(std::shared_ptr<T> value = {}) : value(std::move(value)) {}
        std::shared_ptr<T> load() const
        {
            std::lock_guard lock(mutex);
            return value;
        }
        void store(std::shared_ptr<T> next)
        {
            {
                std::lock_guard lock(mutex);
                value.swap(next);
            }
            // The previous owner's destructor may call back into this slot.
            // Release it after unlocking, just as readers release their copies.
        }

      private:
        mutable std::mutex mutex;
        std::shared_ptr<T> value;
    };
}
