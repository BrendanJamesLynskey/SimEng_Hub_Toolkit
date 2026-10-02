#include <gtest/gtest.h>

#include <tuple>

#include "event_queue.hpp"

// A plain test: no shared setup.
TEST(EventQueue, EarlierEventsComeFirst) {
    EventQueue q;
    q.schedule(2.0, "late");
    q.schedule(1.0, "early");
    EXPECT_EQ(q.pop().name, "early");
    EXPECT_DOUBLE_EQ(q.now(), 1.0);
}

// A fixture: SetUp() runs before every TEST_F that names it.
class TiedQueue : public ::testing::Test {
protected:
    void SetUp() override {
        q.schedule(1.0, "n1");
        q.schedule(1.0, "n2");
        q.schedule(1.0, "urgent", Priority::Urgent);
    }
    EventQueue q;
};

TEST_F(TiedQueue, UrgentBeatsNormalAtTheSameTime) {
    EXPECT_EQ(q.pop().name, "urgent");
}

TEST_F(TiedQueue, EqualKeysAreFirstInFirstOut) {
    q.pop();
    ASSERT_EQ(q.size(), 2u);              // ASSERT stops this test if it fails; EXPECT carries on
    EXPECT_EQ(q.pop().name, "n1");
    EXPECT_EQ(q.pop().name, "n2");
}

// A value-parameterised test: one body, many inputs.
class ClockNeverGoesBack : public ::testing::TestWithParam<std::tuple<double, double, double>> {};

TEST_P(ClockNeverGoesBack, AcrossInsertionOrders) {
    auto [a, b, c] = GetParam();
    EventQueue q;
    for (double t : {a, b, c}) q.schedule(t, "e");
    double last = -1.0;
    while (q.size()) {
        double t = q.pop().time;
        EXPECT_GE(t, last);
        last = t;
    }
}

INSTANTIATE_TEST_SUITE_P(Orders, ClockNeverGoesBack,
                         ::testing::Values(std::make_tuple(1.0, 2.0, 3.0), std::make_tuple(3.0, 2.0, 1.0),
                                           std::make_tuple(2.0, 2.0, 1.0), std::make_tuple(0.0, 0.0, 0.0)));

TEST(EventQueue, SchedulingInThePastThrows) {
    EventQueue q;
    q.schedule(5.0, "x");
    q.pop();
    EXPECT_THROW(q.schedule(4.0, "y"), std::invalid_argument);
}

// A death test: the assertion must abort the process (debug builds only).
TEST(EventQueueDeathTest, PopFromEmptyAborts) {
    EventQueue q;
    EXPECT_DEATH(q.pop(), "empty queue");
}
