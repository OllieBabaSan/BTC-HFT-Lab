from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Level:
    price: float
    size: float


@dataclass(frozen=True)
class Book:
    timestamp_ms: int
    bids: tuple[Level, ...]
    asks: tuple[Level, ...]

    def validate(self) -> None:
        if not self.bids or not self.asks:
            raise ValueError("Both sides of the book are required")
        if self.bids[0].price >= self.asks[0].price:
            raise ValueError("Crossed or locked book")
        if any(level.size <= 0 or level.price <= 0 for level in self.bids + self.asks):
            raise ValueError("Book levels must be positive")


@dataclass(frozen=True)
class TradePrint:
    timestamp_ms: int
    price: float
    size: float
    aggressor: int  # +1 buyer initiated, -1 seller initiated


@dataclass(frozen=True)
class QuoteIntent:
    timestamp_ms: int
    side: int
    price: float
    notional: float
    expected_edge_bps: float
    expires_ms: int

