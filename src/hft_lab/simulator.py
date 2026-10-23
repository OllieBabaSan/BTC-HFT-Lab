from __future__ import annotations

from dataclasses import dataclass

from .config import HftConfig
from .models import QuoteIntent, TradePrint


@dataclass(frozen=True)
class SimulatedFill:
    filled: bool
    fill_price: float | None
    notional: float
    fee: float
    reason: str


@dataclass(frozen=True)
class FillMarkout:
    signed_markout_bps: float
    adverse_selection_bps: float
    gross_pnl: float


def simulate_passive_fill(
    quote: QuoteIntent,
    future_trades: list[TradePrint],
    queue_ahead_notional: float,
    config: HftConfig,
) -> SimulatedFill:
    """Conservative fill: traded notional must first clear estimated queue ahead."""
    if quote.notional > config.max_inventory_notional:
        return SimulatedFill(False, None, 0.0, 0.0, "inventory cap")
    if quote.notional < config.minimum_notional:
        return SimulatedFill(False, None, 0.0, 0.0, "below venue minimum")
    remaining_queue = max(queue_ahead_notional, 0.0)
    eligible_notional = 0.0
    for trade in future_trades:
        if trade.timestamp_ms < quote.timestamp_ms + config.assumed_latency_ms:
            continue
        if trade.timestamp_ms > quote.expires_ms:
            break
        reaches_quote = (quote.side == 1 and trade.price <= quote.price and trade.aggressor == -1) or (quote.side == -1 and trade.price >= quote.price and trade.aggressor == 1)
        if not reaches_quote:
            continue
        traded = trade.price * trade.size
        consumed = min(remaining_queue, traded)
        remaining_queue -= consumed
        eligible_notional += traded - consumed
        if eligible_notional >= quote.notional:
            fee = quote.notional * config.maker_fee
            return SimulatedFill(True, quote.price, quote.notional, fee, "queue cleared")
    partial_notional = min(eligible_notional, quote.notional)
    if partial_notional > 0:
        fee = partial_notional * config.maker_fee
        return SimulatedFill(True, quote.price, partial_notional, fee, "partial fill before cancellation")
    return SimulatedFill(False, None, 0.0, 0.0, "insufficient traded volume after queue")


def mark_passive_fill(fill: SimulatedFill, side: int, future_midpoint: float) -> FillMarkout:
    if not fill.filled or fill.fill_price is None or side not in (-1, 1) or future_midpoint <= 0:
        raise ValueError("A valid fill, side, and future midpoint are required")
    signed_bps = side * (future_midpoint - fill.fill_price) / fill.fill_price * 10_000
    return FillMarkout(
        signed_markout_bps=signed_bps,
        adverse_selection_bps=max(-signed_bps, 0.0),
        gross_pnl=fill.notional * signed_bps / 10_000,
    )
