from __future__ import annotations

import json
from pathlib import Path

from .features import BookFeatures, book_features
from .models import Book, Level, TradePrint


def parse_l2_books(path: str | Path) -> list[Book]:
    books: list[Book] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        payload = record["payload"]
        if payload.get("channel") != "l2Book":
            continue
        data = payload["data"]
        levels = data["levels"]
        if not levels[0] or not levels[1]:
            continue
        book = Book(
            timestamp_ms=int(data["time"]),
            bids=tuple(Level(float(level["px"]), float(level["sz"])) for level in levels[0]),
            asks=tuple(Level(float(level["px"]), float(level["sz"])) for level in levels[1]),
        )
        book.validate()
        books.append(book)
    return sorted(books, key=lambda book: book.timestamp_ms)


def parse_raw_events(path: str | Path) -> tuple[list[BookFeatures], list[TradePrint]]:
    books: list[BookFeatures] = []
    trades: list[TradePrint] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        payload = record["payload"]
        if payload.get("channel") in {"l2Book", "bbo"}:
            data = payload["data"]
            levels = data.get("levels", [[], []]) if payload["channel"] == "l2Book" else [
                [data["bbo"][0]] if data["bbo"][0] else [],
                [data["bbo"][1]] if data["bbo"][1] else [],
            ]
            if not levels[0] or not levels[1]:
                continue
            book = Book(
                timestamp_ms=int(data["time"]),
                bids=tuple(Level(float(level["px"]), float(level["sz"])) for level in levels[0]),
                asks=tuple(Level(float(level["px"]), float(level["sz"])) for level in levels[1]),
            )
            books.append(book_features(book, source=payload["channel"]))
        elif payload.get("channel") == "trades":
            for trade in payload["data"]:
                trades.append(TradePrint(
                    timestamp_ms=int(trade["time"]),
                    price=float(trade["px"]),
                    size=float(trade["sz"]),
                    aggressor=1 if trade["side"] == "B" else -1,
                ))
    return books, trades


def _session_durations(timestamps: list[int], gap_ms: int) -> tuple[int, float, float]:
    if not timestamps:
        return 0, 0.0, 0.0
    ordered = sorted(set(timestamps))
    sessions = 1
    active_ms = 0
    session_start = ordered[0]
    previous = ordered[0]
    for timestamp in ordered[1:]:
        if timestamp - previous > gap_ms:
            active_ms += previous - session_start
            sessions += 1
            session_start = timestamp
        previous = timestamp
    active_ms += previous - session_start
    wall_ms = ordered[-1] - ordered[0]
    return sessions, active_ms / 1000, wall_ms / 1000


def summarize_capture(path: str | Path, session_gap_ms: int = 10_000) -> dict[str, float | int]:
    books, trades = parse_raw_events(path)
    timestamps = [feature.timestamp_ms for feature in books]
    sessions, active_seconds, wall_seconds = _session_durations(timestamps, session_gap_ms)
    l2_updates = sum(feature.source == "l2Book" for feature in books)
    bbo_updates = sum(feature.source == "bbo" for feature in books)
    return {
        "book_updates": len(books),
        "l2_updates": l2_updates,
        "bbo_updates": bbo_updates,
        "trades": len(trades),
        "sessions": sessions,
        "active_duration_seconds": active_seconds,
        "wall_duration_seconds": wall_seconds,
        "book_updates_per_active_second": len(books) / active_seconds if active_seconds else 0.0,
        "trades_per_active_second": len(trades) / active_seconds if active_seconds else 0.0,
        "median_spread_bps": sorted(feature.spread_bps for feature in books)[len(books) // 2] if books else 0.0,
        "mean_absolute_top_imbalance": sum(abs(feature.top_imbalance) for feature in books) / len(books) if books else 0.0,
    }
