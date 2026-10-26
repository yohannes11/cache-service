"""The "transformer function" that stands in for an external service.

The task treats it as slow/expensive, which is the whole reason for caching.
It is wrapped in a class so the service can count calls (proving the cache
works) and so tests can swap in a fake.
"""

import time
from typing import Protocol


class Transformer(Protocol):
    def __call__(self, value: str) -> str: ...


class UppercaseTransformer:
    """Uppercases text, matching the sample output in the task."""

    def __init__(self, latency_seconds: float = 0.0) -> None:
        # Optional artificial delay to make the cost of a cache miss visible
        # during manual testing.
        self.latency_seconds = latency_seconds
        self.calls = 0

    def __call__(self, value: str) -> str:
        self.calls += 1
        if self.latency_seconds:
            time.sleep(self.latency_seconds)
        return value.upper()


# One instance per process so its call counter covers every request.
_default_transformer = UppercaseTransformer()


def get_transformer() -> Transformer:
    """FastAPI dependency; tests override it with a counting fake."""
    return _default_transformer
