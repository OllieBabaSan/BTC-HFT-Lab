from __future__ import annotations

import unittest

from hft_lab.config import HftConfig
from hft_lab.features import book_features
from hft_lab.gates import passive_edge_gate
from hft_lab.models import Book, Level, QuoteIntent, TradePrint
from hft_lab.simulator import mark_passive_fill, simulate_passive_fill


class MicrostructureTests(unittest.TestCase):
    def test_microprice_moves_toward_thin_side(self) -> None:
        book = Book(1, (Level(99, 10),), (Level(101, 1),))
        features = book_features(book)
        self.assertGreater(features.microprice, features.midpoint)
        self.assertGreater(features.top_imbalance, 0)

    def test_stale_data_disables_quote(self) -> None:
        decision = passive_edge_gate(20, 1, 1, 2_000, HftConfig())
        self.assertFalse(decision.eligible)
        self.assertEqual(decision.reason, "stale market data")

    def test_base_maker_fees_are_charged_twice_by_gate(self) -> None:
        # 10 gross bps - 3 round-trip maker fee bps - 1 adverse - 1 inventory = 5.
        decision = passive_edge_gate(10, 1, 1, 100, HftConfig())
        self.assertTrue(decision.eligible)
        self.assertAlmostEqual(decision.net_edge_bps, 5)

    def test_queue_is_consumed_before_our_fill(self) -> None:
        quote = QuoteIntent(1_000, 1, 100, 20, 8, 2_000)
        trades = [TradePrint(1_500, 100, 0.25, -1)]
        partial = simulate_passive_fill(quote, trades, 10, HftConfig())
        self.assertTrue(partial.filled)
        self.assertAlmostEqual(partial.notional, 15)
        fill = simulate_passive_fill(quote, trades, 0, HftConfig())
        self.assertTrue(fill.filled)
        self.assertAlmostEqual(fill.fee, 0.003)

    def test_partial_fill_is_retained_when_quote_expires(self) -> None:
        quote = QuoteIntent(1_000, 1, 100, 20, 8, 2_000)
        trades = [TradePrint(1_500, 100, 0.15, -1)]
        fill = simulate_passive_fill(quote, trades, 5, HftConfig())
        self.assertTrue(fill.filled)
        self.assertEqual(fill.reason, "partial fill before cancellation")
        self.assertAlmostEqual(fill.notional, 10)
        self.assertAlmostEqual(fill.fee, 0.0015)

    def test_post_fill_markout_measures_adverse_selection(self) -> None:
        quote = QuoteIntent(1_000, 1, 100, 20, 8, 2_000)
        fill = simulate_passive_fill(quote, [TradePrint(1_500, 100, 0.2, -1)], 0, HftConfig())
        markout = mark_passive_fill(fill, 1, 99.95)
        self.assertAlmostEqual(markout.signed_markout_bps, -5)
        self.assertAlmostEqual(markout.adverse_selection_bps, 5)
        self.assertAlmostEqual(markout.gross_pnl, -0.01)


if __name__ == "__main__":
    unittest.main()
