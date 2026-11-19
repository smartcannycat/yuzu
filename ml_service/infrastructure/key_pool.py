"""Round-Robin Gemini API key pool with per-key sliding-window RPM and cooldowns."""

import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class GeminiKeyPool:
    """Round-Robin API key pool with concurrency semaphore, per-key RPM, and cooldown."""

    def __init__(
        self,
        api_keys: list[str],
        rpm_limit: int = 5,
        *,
        max_concurrency: int | None = None,
        rpm_window_seconds: float = 0.0,
    ) -> None:
        if rpm_limit < 1:
            raise ValueError("rpm_limit must be at least 1")
        self._api_keys: list[str] = [k.strip() for k in api_keys if k.strip()]
        concurrency = (
            rpm_limit * max(1, len(self._api_keys))
            if max_concurrency is None
            else max(1, max_concurrency)
        )
        self._index: int = 0
        self._key_cooldown_until: dict[str, float] = {}
        self._rpm_limit: int = rpm_limit
        self._rpm_window_seconds: float = max(0.0, rpm_window_seconds)
        self._key_timestamps: dict[str, deque[float]] = {k: deque() for k in self._api_keys}
        self._rate_lock = asyncio.Lock()
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(concurrency)

    def _prune_key_window(self, key: str, cutoff: float) -> deque[float]:
        stamps = self._key_timestamps.setdefault(key, deque())
        while stamps and stamps[0] <= cutoff:
            stamps.popleft()
        return stamps

    def _try_reserve_slot(self, now: float) -> tuple[str | None, float]:
        """Select a key with available per-key RPM headroom, or return wait duration."""
        if not self._api_keys:
            raise RuntimeError("No Gemini API keys configured in GeminiKeyPool.")
        if self._rpm_window_seconds <= 0:
            return self.next_key(), 0.0

        cutoff = now - self._rpm_window_seconds
        total = len(self._api_keys)
        best_wait: float | None = None

        for offset in range(total):
            idx = (self._index + offset) % total
            candidate = self._api_keys[idx]
            if self._key_cooldown_until.get(candidate, 0.0) > now:
                continue
            stamps = self._prune_key_window(candidate, cutoff)
            if len(stamps) < self._rpm_limit:
                stamps.append(now)
                self._index = (idx + 1) % total
                return candidate, 0.0
            wait_candidate = stamps[0] - cutoff + 0.005
            if best_wait is None or wait_candidate < best_wait:
                best_wait = wait_candidate

        if best_wait is not None:
            return None, max(0.005, best_wait)

        # All keys are in 429 cooldown: pick the earliest-expiring key honoring its RPM window.
        earliest = min(self._api_keys, key=lambda k: self._key_cooldown_until.get(k, 0.0))
        stamps = self._prune_key_window(earliest, cutoff)
        if len(stamps) < self._rpm_limit:
            stamps.append(now)
            self._index = (self._api_keys.index(earliest) + 1) % total
            return earliest, 0.0
        return None, max(0.005, stamps[0] - cutoff + 0.005)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[str]:
        """Acquire a concurrency slot and per-key RPM slot, sleeping outside locks."""
        if not self._api_keys:
            raise RuntimeError("No Gemini API keys configured in GeminiKeyPool.")

        while True:
            async with self.semaphore:
                async with self._rate_lock:
                    selected_key, sleep_for = self._try_reserve_slot(time.monotonic())
                if selected_key is not None:
                    yield selected_key
                    return
            await asyncio.sleep(max(0.005, sleep_for))

    @property
    def key_count(self) -> int:
        """Return number of configured non-empty API keys."""
        return len(self._api_keys)

    def is_key_in_cooldown(self, api_key: str) -> bool:
        """Return whether an API key is currently in cooldown."""
        return self._key_cooldown_until.get(api_key, 0.0) > time.monotonic()

    def mark_key_rate_limited(self, api_key: str, cooldown_seconds: float = 30.0) -> None:
        """Place a rate-limited API key on temporary cooldown."""
        if cooldown_seconds > 0 and api_key:
            self._key_cooldown_until[api_key] = time.monotonic() + cooldown_seconds

    def next_key(self) -> str:
        """Return the next healthy API key in Round-Robin order, skipping keys in cooldown."""
        if not self._api_keys:
            raise RuntimeError("No Gemini API keys configured in GeminiKeyPool.")

        now = time.monotonic()
        total = len(self._api_keys)
        for offset in range(total):
            idx = (self._index + offset) % total
            candidate = self._api_keys[idx]
            if self._key_cooldown_until.get(candidate, 0.0) <= now:
                self._index = (idx + 1) % total
                return candidate

        # All keys are in cooldown: return the one whose cooldown expires earliest.
        earliest = min(self._api_keys, key=lambda k: self._key_cooldown_until.get(k, 0.0))
        self._index = (self._api_keys.index(earliest) + 1) % total
        return earliest
