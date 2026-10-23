from __future__ import annotations

from dataclasses import asdict
import math
import statistics

from .features import BookFeatures
from .models import TradePrint


def enrich_order_flow(
    samples: list[BookFeatures],
    trades: list[TradePrint],
    window_ms: int = 5_000,
) -> list[dict[str, float | int | str]]:
    """Attach trailing, strictly contemporaneous trade-flow features to BBO data."""
    ordered_samples = sorted(samples, key=lambda sample: sample.timestamp_ms)
    ordered_trades = sorted(trades, key=lambda trade: trade.timestamp_ms)
    left = right = 0
    rows: list[dict[str, float | int | str]] = []
    for sample in ordered_samples:
        while right < len(ordered_trades) and ordered_trades[right].timestamp_ms <= sample.timestamp_ms:
            right += 1
        cutoff = sample.timestamp_ms - window_ms
        while left < right and ordered_trades[left].timestamp_ms < cutoff:
            left += 1
        window = ordered_trades[left:right]
        notionals = [trade.price * trade.size for trade in window]
        total = sum(notionals)
        signed = sum(notional * trade.aggressor for notional, trade in zip(notionals, window))
        log_returns = [math.log(window[index].price / window[index - 1].price) for index in range(1, len(window))]
        row = asdict(sample)
        row.update({
            "flow_window_ms": window_ms,
            "trade_count": len(window),
            "trade_notional": total,
            "signed_notional": signed,
            "flow_imbalance": signed / total if total else 0.0,
            "trade_volatility_bps": statistics.pstdev(log_returns) * 10_000 if len(log_returns) > 1 else 0.0,
        })
        rows.append(row)
    return rows

