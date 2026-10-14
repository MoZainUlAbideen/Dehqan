"""Tiny in-memory fixed-window rate limiter, one counter per client key (IP).

Good enough for a single-instance free-tier demo. It resets when the process restarts and is NOT shared
between instances; a multi-instance deploy would need Redis.
"""

import time
from typing import Callable


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.max_requests, self.window, self.clock = max_requests, window_seconds, clock
        self._hits: dict[str, tuple[float, int]] = {}  # key -> (window_start, count)

    def allow(self, key: str) -> bool:
        now = self.clock()
        start, count = self._hits.get(key, (now, 0))
        if now - start >= self.window:
            start, count = now, 0
        if count >= self.max_requests:
            self._hits[key] = (start, count)
            return False
        self._hits[key] = (start, count + 1)
        if len(self._hits) > 10_000:  # bound memory: drop expired windows
            self._hits = {k: v for k, v in self._hits.items() if now - v[0] < self.window}
        return True
