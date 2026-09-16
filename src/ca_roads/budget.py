"""Daily counters for paid upstreams and per-client caps.

Every token bucket in this codebase bounds the rate; nothing bounded
the day. A client at two requests a second for a day is 170k geocodes,
and a paid upstream (Stadia, TomTom) bills or blackouts on the total.
One in-process counter per key, reset at UTC midnight, is the cheapest
guard that closes that: it resets on restart, which only ever makes
the caps more generous, and the services run one instance each.
"""

from __future__ import annotations

from datetime import UTC, datetime


class DailyCounter:
    """Counts per key for the current UTC day."""

    def __init__(self, max_keys: int = 10_000) -> None:
        self.day = ""
        self.counts: dict[str, int] = {}
        self.max_keys = max_keys

    def _roll(self) -> None:
        today = datetime.now(UTC).date().isoformat()
        if today != self.day:
            self.day = today
            self.counts = {}

    def used(self, key: str) -> int:
        self._roll()
        return self.counts.get(key, 0)

    def allow(self, key: str, limit: int) -> bool:
        """Count one use of ``key``; False once ``limit`` is reached."""
        self._roll()
        n = self.counts.get(key, 0)
        if n >= limit:
            return False
        if n == 0 and len(self.counts) >= self.max_keys:
            # Drop the least-used half; a flood of fresh keys must not
            # grow without bound.
            stale = sorted(self.counts.items(), key=lambda kv: kv[1])
            for k, _ in stale[: len(stale) // 2 + 1]:
                del self.counts[k]
        self.counts[key] = n + 1
        return True


# Global budgets for paid upstreams, keyed by upstream name. Shared by
# both services through the modules that make the calls.
UPSTREAM = DailyCounter()
