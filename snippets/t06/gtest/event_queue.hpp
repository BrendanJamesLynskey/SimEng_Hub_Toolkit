// A C++ event queue with the kernel's ordering rule: time, then priority, then FIFO.
#pragma once
#include <cassert>
#include <cstdint>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

enum class Priority : int { Urgent = 0, Normal = 1 };

struct Event {
    double time;
    Priority priority;
    std::uint64_t seq;
    std::string name;
};

// std::priority_queue is a max-heap, so the comparator says which event is *later*.
struct Later {
    bool operator()(const Event& a, const Event& b) const {
        if (a.time != b.time) return a.time > b.time;
        if (a.priority != b.priority) return a.priority > b.priority;
        return a.seq > b.seq;
    }
};

class EventQueue {
public:
    void schedule(double t, std::string name, Priority p = Priority::Normal) {
        if (t < now_) throw std::invalid_argument("event scheduled in the past");
        heap_.push({t, p, seq_++, std::move(name)});
    }
    Event pop() {
        assert(!heap_.empty() && "pop from an empty queue");
        Event e = heap_.top();
        heap_.pop();
        now_ = e.time;
        return e;
    }
    double now() const { return now_; }
    std::size_t size() const { return heap_.size(); }

private:
    double now_ = 0.0;
    std::uint64_t seq_ = 0;
    std::priority_queue<Event, std::vector<Event>, Later> heap_;
};
