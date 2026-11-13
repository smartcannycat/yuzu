import asyncio
import time


class GeminiKeyPool:
    """Round-Robin API key pool with concurrency semaphore and 429 cooldown tracking."""

    def __init__(self, api_keys: list[str], rpm_limit: int = 5) -> None:
        if rpm_limit < 1:
            raise ValueError("rpm_limit must be at least 1")
        self._api_keys: list[str] = [k.strip() for k in api_keys if k.strip()]
        self._index: int = 0
        self._key_cooldown_until: dict[str, float] = {}
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(rpm_limit)

    @property
    def key_count(self) -> int:
        """Return number of configured non-empty API keys."""
        return len(self._api_keys)

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
