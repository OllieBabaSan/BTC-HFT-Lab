from __future__ import annotations

from dataclasses import dataclass

from .models import Book


@dataclass(frozen=True)
class BookFeatures:
    timestamp_ms: int
    midpoint: float
    spread_bps: float
    microprice: float
    microprice_edge_bps: float
    top_imbalance: float
    depth_imbalance: float
    source: str = "l2Book"


def _imbalance(bid_size: float, ask_size: float) -> float:
    total = bid_size + ask_size
    return (bid_size - ask_size) / total if total else 0.0


def book_features(book: Book, depth: int = 5, source: str = "l2Book") -> BookFeatures:
    book.validate()
    bid, ask = book.bids[0], book.asks[0]
    midpoint = (bid.price + ask.price) / 2
    spread_bps = (ask.price - bid.price) / midpoint * 10_000
    # Opposite-side weighting estimates where the next efficient price lies.
    microprice = (ask.price * bid.size + bid.price * ask.size) / (bid.size + ask.size)
    bid_depth = sum(level.size for level in book.bids[:depth])
    ask_depth = sum(level.size for level in book.asks[:depth])
    return BookFeatures(
        timestamp_ms=book.timestamp_ms,
        midpoint=midpoint,
        spread_bps=spread_bps,
        microprice=microprice,
        microprice_edge_bps=(microprice - midpoint) / midpoint * 10_000,
        top_imbalance=_imbalance(bid.size, ask.size),
        depth_imbalance=_imbalance(bid_depth, ask_depth),
        source=source,
    )
