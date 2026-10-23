from __future__ import annotations

import unittest

from hft_lab.features import BookFeatures
from hft_lab.models import TradePrint
from hft_lab.screening import screen_order_flow


class ScreeningTests(unittest.TestCase):
    def test_order_flow_screen_uses_non_overlapping_signals(self) -> None:
        samples = [
            BookFeatures(time, price, 1, price, 0, 0, 0, "bbo")
            for time, price in ((1_000, 100), (1_500, 100), (2_000, 101), (3_000, 102))
        ]
        trades = [
            TradePrint(900, 100, 1, 1),
            TradePrint(950, 100, 1, 1),
            TradePrint(1_000, 100, 1, 1),
        ]
        result = screen_order_flow(
            samples, trades, horizon_ms=1_000, minimum_absolute_imbalance=0.5,
            minimum_trades=3, cooldown_ms=1_000,
        )
        self.assertEqual(result.observations, 2)
        self.assertGreater(result.mean_signed_return_bps, 0)

    def test_order_flow_screen_rejects_weak_flow(self) -> None:
        samples = [
            BookFeatures(1_000, 100, 1, 100, 0, 0, 0, "bbo"),
            BookFeatures(2_000, 101, 1, 101, 0, 0, 0, "bbo"),
        ]
        trades = [TradePrint(1_000, 100, 1, 1)]
        result = screen_order_flow(samples, trades, 1_000, minimum_trades=2)
        self.assertEqual(result.observations, 0)
