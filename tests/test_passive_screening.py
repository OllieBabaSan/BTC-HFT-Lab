from __future__ import annotations

import unittest

from hft_lab.config import HftConfig
from hft_lab.features import BookFeatures
from hft_lab.models import Book, Level, TradePrint
from hft_lab.passive_screening import screen_passive_quotes


class PassiveScreeningTests(unittest.TestCase):
    def test_queue_ahead_prevents_optimistic_fill(self) -> None:
        book = Book(1_000, (Level(99, 1),), (Level(101, 1),))
        samples = [BookFeatures(6_000, 100, 1, 100, 0, 0, 0, "bbo")]
        trades = [TradePrint(1_500, 99, 0.2, -1)]
        blocked = screen_passive_quotes([book], samples, trades, HftConfig(), queue_multiplier=1)
        permissive = screen_passive_quotes([book], samples, trades, HftConfig(), queue_multiplier=0)
        self.assertEqual(blocked.fills, 0)
        self.assertEqual(permissive.fills, 1)

    def test_after_cost_result_charges_maker_entry_and_taker_exit(self) -> None:
        book = Book(1_000, (Level(99, 1),), (Level(101, 1),))
        samples = [BookFeatures(6_000, 100, 1, 100, 0, 0, 0, "bbo")]
        trades = [TradePrint(1_500, 99, 0.2, -1)]
        result = screen_passive_quotes([book], samples, trades, HftConfig(), queue_multiplier=0)
        self.assertAlmostEqual(result.mean_after_entry_and_exit_fees_bps, 95.010101, places=5)
