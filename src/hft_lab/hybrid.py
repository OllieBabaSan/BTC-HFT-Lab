from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .features import BookFeatures, book_features
from .cross_venue import ReferenceQuote, basis_adjusted_displacements, displacement_features
from .models import Book, Level, TradePrint
from .order_flow import enrich_order_flow


@dataclass(frozen=True)
class DepthState:
    features: BookFeatures
    bid_depth: float
    ask_depth: float


def parse_hybrid_hyperliquid(path: str | Path, depth: int = 5) -> tuple[list[DepthState], list[TradePrint]]:
    books: list[DepthState] = []
    trades: list[TradePrint] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("venue") != "hyperliquid":
            continue
        message = record["payload"]
        channel = record.get("channel")
        received_at = int(record["receivedAtMs"])
        if channel == "l2Book":
            levels = message["data"]["levels"]
            if not levels[0] or not levels[1]:
                continue
            book = Book(
                timestamp_ms=received_at,
                bids=tuple(Level(float(item["px"]), float(item["sz"])) for item in levels[0]),
                asks=tuple(Level(float(item["px"]), float(item["sz"])) for item in levels[1]),
            )
            books.append(DepthState(
                features=book_features(book, depth=depth, source="l2Book"),
                bid_depth=sum(level.size for level in book.bids[:depth]),
                ask_depth=sum(level.size for level in book.asks[:depth]),
            ))
        elif channel == "trades":
            for item in message["data"]:
                trades.append(TradePrint(
                    timestamp_ms=received_at,
                    price=float(item["px"]),
                    size=float(item["sz"]),
                    aggressor=1 if item["side"] == "B" else -1,
                ))
    return sorted(books, key=lambda state: state.features.timestamp_ms), sorted(trades, key=lambda trade: trade.timestamp_ms)


def depth_depletion(states: list[DepthState], max_gap_ms: int = 7_500) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    ordered = sorted(states, key=lambda state: state.features.timestamp_ms)
    for previous, current in zip(ordered, ordered[1:]):
        elapsed = current.features.timestamp_ms - previous.features.timestamp_ms
        if elapsed <= 0 or elapsed > max_gap_ms or previous.bid_depth <= 0 or previous.ask_depth <= 0:
            continue
        bid_change = (current.bid_depth - previous.bid_depth) / previous.bid_depth
        ask_change = (current.ask_depth - previous.ask_depth) / previous.ask_depth
        rows.append({
            "timestamp_ms": current.features.timestamp_ms,
            "elapsed_ms": elapsed,
            "depth_imbalance": current.features.depth_imbalance,
            "bid_depth_change": bid_change,
            "ask_depth_change": ask_change,
            "depletion_pressure": bid_change - ask_change,
        })
    return rows


def assemble_hybrid_rows(
    states: list[DepthState],
    trades: list[TradePrint],
    reference: list[ReferenceQuote],
    flow_window_ms: int = 5_000,
    basis_lookback_ms: int = 60_000,
    minimum_basis_history: int = 10,
) -> list[dict[str, float | int | str]]:
    """Causally align all hybrid inputs at each L2 receipt timestamp."""
    samples = [state.features for state in states]
    displacement = displacement_features(samples, reference)
    adjusted = basis_adjusted_displacements(displacement, basis_lookback_ms, minimum_basis_history)
    flow = enrich_order_flow(samples, trades, flow_window_ms)
    depletion = depth_depletion(states)
    adjusted_by_time = {int(row["timestamp_ms"]): row for row in adjusted}
    flow_by_time = {int(row["timestamp_ms"]): row for row in flow}
    depletion_by_time = {int(row["timestamp_ms"]): row for row in depletion}
    rows: list[dict[str, float | int | str]] = []
    for timestamp in sorted(adjusted_by_time.keys() & flow_by_time.keys() & depletion_by_time.keys()):
        cross = adjusted_by_time[timestamp]
        order_flow = flow_by_time[timestamp]
        depth = depletion_by_time[timestamp]
        rows.append({
            "timestamp_ms": timestamp,
            "midpoint": float(cross["hyperliquid_midpoint"]),
            "reference_age_ms": int(cross["reference_age_ms"]),
            "basis_residual_bps": float(cross["basis_residual_bps"]),
            "depth_imbalance": float(depth["depth_imbalance"]),
            "depletion_pressure": float(depth["depletion_pressure"]),
            "flow_imbalance": float(order_flow["flow_imbalance"]),
            "trade_count": int(order_flow["trade_count"]),
            "trade_volatility_bps": float(order_flow["trade_volatility_bps"]),
        })
    return rows
