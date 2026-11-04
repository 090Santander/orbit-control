"""Bounded, short-lived input queue; never replays commands after reconnection."""
from collections import deque
import time


class CommandQueue:
    def __init__(self, capacity=8, lifetime=2.0):
        self.capacity = capacity
        self.lifetime = lifetime
        self.items = deque()
        self.expired = 0

    def __len__(self):
        return len(self.items)

    def push(self, action, now=None):
        if len(self.items) >= self.capacity:
            return False
        self.items.append((time.monotonic() if now is None else now, action))
        return True

    def pop(self, now=None):
        now = time.monotonic() if now is None else now
        while self.items:
            stamp, action = self.items.popleft()
            if now - stamp <= self.lifetime:
                return action
            self.expired += 1
        return None

    def clear(self):
        count = len(self.items)
        self.items.clear()
        return count
