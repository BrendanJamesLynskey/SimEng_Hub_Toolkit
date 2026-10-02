"""Stateful property test: Hypothesis drives random sequences of schedule/pop
calls and checks the queue against a deliberately simple model after every step."""

import os

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from event_queue import NORMAL, URGENT, EventQueue

FIFO = os.environ.get("QUEUE_BUG") != "lifo"


class EventQueueMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.q = EventQueue(fifo_ties=FIFO)
        self.model = []          # (time, priority, insertion order, name): sorted() is the spec
        self.n = 0

    @rule(dt=st.integers(0, 3), urgent=st.booleans())
    def schedule(self, dt, urgent):
        prio = URGENT if urgent else NORMAL
        name = f"e{self.n}"
        self.q.schedule(self.q.now + dt, name, prio)
        self.model.append((self.q.now + dt, prio, self.n, name))
        self.n += 1

    @precondition(lambda self: self.model)
    @rule()
    def pop(self):
        want = min(self.model)
        self.model.remove(want)
        assert self.q.pop() == (want[0], want[3])

    @invariant()
    def sizes_agree(self):
        assert len(self.q) == len(self.model)


TestEventQueue = EventQueueMachine.TestCase
