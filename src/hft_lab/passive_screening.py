from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from .config import HftConfig
from .features import BookFeatures
from .models import Book, QuoteIntent, TradePrint
from .simulator import mark_passive_fill, simulate_passive_fill


@dataclass(frozen=True)
class PassiveScreen:
    quotes: int
    fills: int
    partial_fills: int
    fill_rate: float
    mean_markout_bps: float | None
    mean_after_entry_and_exit_fees_bps: float | None
    positive_after_costs: int


def screen_passive_quotes(
    books: list[Book],
    midpoint_samples: list[BookFeatures],
    trades: list[TradePrint],
    config: HftConfig,
    queue_multiplier: float = 1.0,
    quote_notional: float = 20.0,
    expiry_ms: int = 2_000,
    markout_ms: int = 5_000,
    max_markout_lateness_ms: int = 1_000,
) -> PassiveScreen:
    samples = sorted(midpoint_samples, key=lambda sample: sample.timestamp_ms)
    sample_times = [sample.timestamp_ms for sample in samples]
    ordered_trades = sorted(trades, key=lambda trade: trade.timestamp_ms)
    markouts: list[float] = []
    fills = partials = positives = quotes = 0
    total_cost_bps = (config.maker_fee + config.taker_fee) * 10_000
    for book in books:
        future = [trade for trade in ordered_trades if book.timestamp_ms <= trade.timestamp_ms <= book.timestamp_ms + expiry_ms]
        target = book.timestamp_ms + markout_ms
        future_index = bisect_left(sample_times, target)
        if future_index >= len(samples) or sample_times[future_index] > target + max_markout_lateness_ms:
            continue
        future_midpoint = samples[future_index].midpoint
        for side, level in ((1, book.bids[0]), (-1, book.asks[0])):
            quotes += 1
            intent = QuoteIntent(book.timestamp_ms, side, level.price, quote_notional, 0.0, book.timestamp_ms + expiry_ms)
            fill = simulate_passive_fill(
                intent, future, level.price * level.size * queue_multiplier, config,
            )
            if not fill.filled:
                continue
            fills += 1
            partials += fill.notional < quote_notional
            markout = mark_passive_fill(fill, side, future_midpoint).signed_markout_bps
            markouts.append(markout)
            positives += markout > total_cost_bps
    return PassiveScreen(
        quotes=quotes,
        fills=fills,
        partial_fills=partials,
        fill_rate=fills / quotes if quotes else 0.0,
        mean_markout_bps=sum(markouts) / fills if fills else None,
        mean_after_entry_and_exit_fees_bps=(sum(markouts) / fills - total_cost_bps) if fills else None,
        positive_after_costs=positives,
    )
