from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
import json
from pathlib import Path

from .features import BookFeatures
from .features import book_features
from .models import Book, Level


@dataclass(frozen=True)
class ReferenceQuote:
    received_at_ms: int
    exchange_time_ms: int | None
    bid: float
    ask: float

    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2


def parse_binance_quotes(path: str | Path) -> list[ReferenceQuote]:
    quotes: list[ReferenceQuote] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("venue") != "binance" or record.get("channel") != "bookTicker":
            continue
        payload = record["payload"]
        bid, ask = float(payload["b"]), float(payload["a"])
        if bid <= 0 or ask <= bid:
            continue
        exchange_time = payload.get("E")
        quotes.append(ReferenceQuote(
            received_at_ms=int(record["receivedAtMs"]),
            exchange_time_ms=int(exchange_time) if exchange_time is not None else None,
            bid=bid,
            ask=ask,
        ))
    return sorted(quotes, key=lambda quote: quote.received_at_ms)


def parse_hyperliquid_bbo_receipts(path: str | Path) -> list[BookFeatures]:
    samples: list[BookFeatures] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("venue") != "hyperliquid" or record.get("channel") != "bbo":
            continue
        message = record["payload"]
        data = message["data"]
        bid, ask = data["bbo"]
        if not bid or not ask:
            continue
        book = Book(
            timestamp_ms=int(record["receivedAtMs"]),
            bids=(Level(float(bid["px"]), float(bid["sz"])),),
            asks=(Level(float(ask["px"]), float(ask["sz"])),),
        )
        samples.append(book_features(book, source="hyperliquid_bbo_receipt"))
    return sorted(samples, key=lambda sample: sample.timestamp_ms)


def displacement_features(
    hyperliquid: list[BookFeatures],
    reference: list[ReferenceQuote],
    max_reference_age_ms: int = 1_000,
) -> list[dict[str, float | int | str]]:
    """Join only the latest reference quote received at or before each HL observation."""
    ordered_reference = sorted(reference, key=lambda quote: quote.received_at_ms)
    receipt_times = [quote.received_at_ms for quote in ordered_reference]
    rows: list[dict[str, float | int | str]] = []
    for sample in sorted(hyperliquid, key=lambda item: item.timestamp_ms):
        index = bisect_right(receipt_times, sample.timestamp_ms) - 1
        if index < 0:
            continue
        quote = ordered_reference[index]
        age_ms = sample.timestamp_ms - quote.received_at_ms
        if age_ms > max_reference_age_ms:
            continue
        rows.append({
            "timestamp_ms": sample.timestamp_ms,
            "source": sample.source,
            "hyperliquid_midpoint": sample.midpoint,
            "reference_midpoint": quote.midpoint,
            "reference_age_ms": age_ms,
            "displacement_bps": (quote.midpoint - sample.midpoint) / sample.midpoint * 10_000,
        })
    return rows


def basis_adjusted_displacements(
    rows: list[dict[str, float | int | str]],
    lookback_ms: int = 60_000,
    minimum_history: int = 20,
) -> list[dict[str, float | int | str]]:
    """Subtract a trailing median using strictly earlier observations."""
    ordered = sorted(rows, key=lambda row: int(row["timestamp_ms"]))
    adjusted: list[dict[str, float | int | str]] = []
    start = 0
    for index, row in enumerate(ordered):
        timestamp = int(row["timestamp_ms"])
        while start < index and int(ordered[start]["timestamp_ms"]) < timestamp - lookback_ms:
            start += 1
        history = [float(item["displacement_bps"]) for item in ordered[start:index]]
        if len(history) < minimum_history:
            continue
        history.sort()
        middle = len(history) // 2
        baseline = history[middle] if len(history) % 2 else (history[middle - 1] + history[middle]) / 2
        enriched = dict(row)
        enriched["basis_baseline_bps"] = baseline
        enriched["basis_residual_bps"] = float(row["displacement_bps"]) - baseline
        adjusted.append(enriched)
    return adjusted


def label_hyperliquid_forward_returns(
    rows: list[dict[str, float | int | str]],
    hyperliquid: list[BookFeatures],
    horizons_ms: tuple[int, ...] = (1_000, 5_000, 30_000),
    max_lateness_ms: int = 1_000,
) -> list[dict[str, float | int | str | None]]:
    samples = sorted(hyperliquid, key=lambda item: item.timestamp_ms)
    timestamps = [sample.timestamp_ms for sample in samples]
    labelled: list[dict[str, float | int | str | None]] = []
    for row in rows:
        enriched: dict[str, float | int | str | None] = dict(row)
        timestamp = int(row["timestamp_ms"])
        current_index = bisect_right(timestamps, timestamp) - 1
        if current_index < 0:
            continue
        current_midpoint = samples[current_index].midpoint
        for horizon in horizons_ms:
            target = timestamp + horizon
            future_index = bisect_left(timestamps, target)
            key = f"forward_{horizon}ms_bps"
            if future_index >= len(samples) or timestamps[future_index] > target + max_lateness_ms:
                enriched[key] = None
            else:
                enriched[key] = (samples[future_index].midpoint - current_midpoint) / current_midpoint * 10_000
        labelled.append(enriched)
    return labelled
