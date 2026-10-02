"""A Python event queue with the kernel's ordering rule: time, then priority, then FIFO."""

import heapq
import itertools

URGENT, NORMAL = 0, 1


class EventQueue:
    def __init__(self, fifo_ties: bool = True):
        self.now = 0.0
        self._heap = []
        self._seq = itertools.count()
        self._sign = 1 if fifo_ties else -1        # -1 is the bug: last in, first out

    def schedule(self, t: float, event, priority: int = NORMAL):
        if t < self.now:
            raise ValueError("event scheduled in the past")
        heapq.heappush(self._heap, (t, priority, self._sign * next(self._seq), event))

    def pop(self):
        t, _, _, event = heapq.heappop(self._heap)
        self.now = t
        return t, event

    def __len__(self):
        return len(self._heap)
