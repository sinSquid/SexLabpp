#include "AsyncIO.h"

#include <chrono>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>

namespace Util::AsyncIO
{
    namespace
    {
        using namespace std::chrono_literals;

        class TaskConsumer final
        {
          public:
            ~TaskConsumer()
            {
                _worker.request_stop();
                _condition.notify_all();
                if (_worker.joinable())
                    _worker.join();
            }

            void Submit(std::move_only_function<void()> a_task)
            {
                {
                    std::lock_guard lock{ _mutex };
                    if (!_running) {
                        if (_worker.joinable())
                            _worker.join();
                        _worker = std::jthread([this](std::stop_token a_stopToken) { Run(a_stopToken); });
                        _running = true;
                    }
                    _tasks.emplace_back(std::move(a_task));
                }
                _condition.notify_one();
            }

          private:
            void Run(std::stop_token a_stopToken)
            {
                std::unique_lock lock{ _mutex };
                for (;;) {
                    if (_tasks.empty() &&
                        !_condition.wait_for(lock, a_stopToken, 2s, [this]() { return !_tasks.empty(); })) {
                        _running = false;
                        return;
                    }
                    auto task = std::move(_tasks.front());
                    _tasks.pop_front();
                    lock.unlock();
                    try {
                        task();
                    } catch (const std::exception& e) {
                        logger::error("Async I/O task failed: {}", e.what());
                    } catch (...) {
                        logger::error("Async I/O task failed with an unknown exception");
                    }
                    lock.lock();
                }
            }

            std::mutex _mutex;
            std::condition_variable_any _condition;
            std::deque<std::move_only_function<void()>> _tasks;
            bool _running{ false };
            std::jthread _worker;
        };
    }

    void Submit(std::move_only_function<void()> a_task)
    {
        static TaskConsumer consumer;
        consumer.Submit(std::move(a_task));
    }
}
