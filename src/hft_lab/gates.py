from __future__ import annotations

from dataclasses import dataclass

from .config import HftConfig


@dataclass(frozen=True)
class EdgeDecision:
    eligible: bool
    net_edge_bps: float
    reason: str


def passive_edge_gate(
    gross_edge_bps: float,
    adverse_selection_bps: float,
    inventory_cost_bps: float,
    data_age_ms: int,
    config: HftConfig,
) -> EdgeDecision:
    if data_age_ms > config.stale_after_ms:
        return EdgeDecision(False, float("-inf"), "stale market data")
    fee_bps = 2 * config.maker_fee * 10_000
    net = gross_edge_bps - fee_bps - adverse_selection_bps - inventory_cost_bps
    if net < config.minimum_edge_bps:
        return EdgeDecision(False, net, "edge does not clear costs and safety margin")
    return EdgeDecision(True, net, "eligible")

