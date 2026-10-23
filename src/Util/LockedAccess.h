#pragma once
#include <mutex>
#include <utility>

namespace Util
{
    // Keep the lookup lock alive until the caller has finished using the object.
    template<class T, class Lock>
    class LockedAccess
    {
      public:
        LockedAccess(Lock&& lock, T* value) : lock_(std::move(lock)), value_(value) {}
        LockedAccess(LockedAccess&& other) noexcept :
            lock_(std::move(other.lock_)), value_(std::exchange(other.value_, nullptr)) {}
        LockedAccess& operator=(LockedAccess&& other) noexcept
        {
            if (this != &other) {
                lock_ = std::move(other.lock_);
                value_ = std::exchange(other.value_, nullptr);
            }
            return *this;
        }
        LockedAccess(const LockedAccess&) = delete;
        LockedAccess& operator=(const LockedAccess&) = delete;
        explicit operator bool() const noexcept { return value_ != nullptr; }
        T* get() const noexcept { return value_; }
        T* operator->() const noexcept { return value_; }
        T& operator*() const noexcept { return *value_; }
      private:
        Lock lock_;
        T* value_;
    };
}
