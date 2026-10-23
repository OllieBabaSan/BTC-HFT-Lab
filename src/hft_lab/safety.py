from __future__ import annotations

from dataclasses import dataclass, field

from .config import HftConfig


@dataclass
class FeedState:
    connected: bool = False
    last_received_ms: int | None = None


@dataclass
class DeadManGate:
    required_feeds: tuple[str, ...]
    feeds: dict[str, FeedState] = field(default_factory=dict)
    violations: int = 0
    last_reason: str = "not initialized"

    def connect(self, feed: str) -> None:
        self.feeds.setdefault(feed, FeedState()).connected = True

    def disconnect(self, feed: str) -> None:
        self.feeds.setdefault(feed, FeedState()).connected = False

    def observe(self, feed: str, received_at_ms: int) -> None:
        state = self.feeds.setdefault(feed, FeedState())
        state.connected = True
        state.last_received_ms = received_at_ms

    def eligible(self, now_ms: int, config: HftConfig) -> bool:
        for feed in self.required_feeds:
            state = self.feeds.get(feed)
            if state is None or not state.connected:
                self.violations += 1
                self.last_reason = f"{feed} disconnected"
                return False
            age_ms = now_ms - state.last_received_ms if state.last_received_ms is not None else None
            if age_ms is None or age_ms < 0 or age_ms > config.stale_after_ms:
                self.violations += 1
                self.last_reason = f"{feed} invalid timestamp" if age_ms is not None and age_ms < 0 else f"{feed} stale"
                return False
        self.last_reason = "eligible"
        return True
