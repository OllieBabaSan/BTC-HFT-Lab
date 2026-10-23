from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GoNoGoEvidence:
    out_of_sample_sessions: int
    completed_round_trips: int
    net_pnl: float
    profit_factor: float
    maximum_drawdown: float
    stale_or_safety_violations: int


def go_no_go(evidence: GoNoGoEvidence) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    if evidence.out_of_sample_sessions < 5:
        failures.append("fewer than five out-of-sample sessions")
    if evidence.completed_round_trips < 100:
        failures.append("fewer than 100 out-of-sample round trips")
    if evidence.net_pnl <= 0:
        failures.append("non-positive net PnL after costs")
    if evidence.profit_factor < 1.2:
        failures.append("profit factor below 1.2")
    if evidence.maximum_drawdown < -0.10:
        failures.append("drawdown exceeded 10%")
    if evidence.stale_or_safety_violations:
        failures.append("stale-data or safety violation observed")
    return not failures, tuple(failures)
