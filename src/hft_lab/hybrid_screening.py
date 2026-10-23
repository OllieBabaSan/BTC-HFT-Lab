from __future__ import annotations

from dataclasses import dataclass

from .features import BookFeatures
from .labels import label_forward_returns


@dataclass(frozen=True)
class HybridScreen:
    eligible: int
    observations: int
    mean_signed_return_bps: float | None
    hit_rate: float | None
    moves_over_cost: int


def screen_hybrid(
    rows: list[dict[str, float | int | str]],
    bbo_samples: list[BookFeatures],
    horizon_ms: int = 5_000,
    minimum_residual_bps: float = 0.5,
    minimum_flow_imbalance: float = 0.3,
    minimum_depletion: float = 0.05,
    minimum_depth_imbalance: float = 0.1,
    minimum_volatility_bps: float = 0.0,
    maximum_volatility_bps: float = 10.0,
    minimum_trades: int = 3,
    round_trip_cost_bps: float = 9.0,
) -> HybridScreen:
    label_rows = label_forward_returns(bbo_samples, (horizon_ms,))
    labels = {int(row["timestamp_ms"]): row[f"forward_{horizon_ms}ms_bps"] for row in label_rows}
    # Hybrid decision timestamps are L2 receipts, so find the first BBO label timestamp
    # at or after each decision without letting decisions overlap.
    ordered_labels = sorted(labels)
    signed_returns: list[float] = []
    eligible = 0
    next_eligible = -1
    for row in sorted(rows, key=lambda item: int(item["timestamp_ms"])):
        timestamp = int(row["timestamp_ms"])
        residual = float(row["basis_residual_bps"])
        flow = float(row["flow_imbalance"])
        depletion = float(row["depletion_pressure"])
        depth_imbalance = float(row["depth_imbalance"])
        volatility = float(row["trade_volatility_bps"])
        if int(row["trade_count"]) < minimum_trades:
            continue
        if (
            abs(residual) < minimum_residual_bps
            or abs(flow) < minimum_flow_imbalance
            or abs(depletion) < minimum_depletion
            or abs(depth_imbalance) < minimum_depth_imbalance
            or not minimum_volatility_bps <= volatility <= maximum_volatility_bps
        ):
            continue
        directions = (
            1 if residual > 0 else -1,
            1 if flow > 0 else -1,
            1 if depletion > 0 else -1,
            1 if depth_imbalance > 0 else -1,
        )
        if len(set(directions)) != 1:
            continue
        eligible += 1
        if timestamp < next_eligible:
            continue
        label_time = next((value for value in ordered_labels if value >= timestamp), None)
        if label_time is None or labels[label_time] is None or label_time - timestamp > 1_000:
            continue
        signed_returns.append(directions[0] * float(labels[label_time]))
        next_eligible = timestamp + horizon_ms
    count = len(signed_returns)
    return HybridScreen(
        eligible=eligible,
        observations=count,
        mean_signed_return_bps=sum(signed_returns) / count if count else None,
        hit_rate=sum(value > 0 for value in signed_returns) / count if count else None,
        moves_over_cost=sum(value > round_trip_cost_bps for value in signed_returns),
    )
