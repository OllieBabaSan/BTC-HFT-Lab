from __future__ import annotations

from dataclasses import dataclass

from .features import BookFeatures
from .labels import label_forward_returns
from .models import TradePrint
from .order_flow import enrich_order_flow


@dataclass(frozen=True)
class DirectionalScreen:
    horizon_ms: int
    observations: int
    mean_signed_return_bps: float | None
    hit_rate: float | None
    gross_moves_over_cost: int


def screen_order_flow(
    samples: list[BookFeatures],
    trades: list[TradePrint],
    horizon_ms: int,
    flow_window_ms: int = 5_000,
    minimum_absolute_imbalance: float = 0.5,
    minimum_trades: int = 3,
    round_trip_cost_bps: float = 9.0,
    cooldown_ms: int | None = None,
) -> DirectionalScreen:
    """Non-overlapping directional screen with features based only on trailing trades."""
    bbo = sorted((sample for sample in samples if sample.source == "bbo"), key=lambda item: item.timestamp_ms)
    flow = enrich_order_flow(bbo, trades, flow_window_ms)
    labels = label_forward_returns(bbo, (horizon_ms,))
    label_key = f"forward_{horizon_ms}ms_bps"
    cooldown = horizon_ms if cooldown_ms is None else cooldown_ms
    signed_returns: list[float] = []
    next_eligible_ms = -1
    for feature, label in zip(flow, labels):
        timestamp = int(feature["timestamp_ms"])
        forward = label[label_key]
        imbalance = float(feature["flow_imbalance"])
        if timestamp < next_eligible_ms or forward is None:
            continue
        if int(feature["trade_count"]) < minimum_trades or abs(imbalance) < minimum_absolute_imbalance:
            continue
        direction = 1 if imbalance > 0 else -1
        signed_returns.append(direction * float(forward))
        next_eligible_ms = timestamp + cooldown
    count = len(signed_returns)
    return DirectionalScreen(
        horizon_ms=horizon_ms,
        observations=count,
        mean_signed_return_bps=sum(signed_returns) / count if count else None,
        hit_rate=sum(value > 0 for value in signed_returns) / count if count else None,
        gross_moves_over_cost=sum(value > round_trip_cost_bps for value in signed_returns),
    )
