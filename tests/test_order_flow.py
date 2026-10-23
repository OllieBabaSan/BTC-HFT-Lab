from __future__ import annotations

import unittest

from hft_lab.features import BookFeatures
from hft_lab.models import TradePrint
from hft_lab.order_flow import enrich_order_flow


class OrderFlowTests(unittest.TestCase):
    def test_uses_only_trades_in_trailing_window(self) -> None:
        sample = BookFeatures(10_000, 100, 1, 100, 0, 0, 0, "bbo")
        trades = [
            TradePrint(4_000, 100, 1, -1),
            TradePrint(6_000, 100, 1, 1),
            TradePrint(9_000, 100, 2, -1),
            TradePrint(11_000, 100, 100, 1),
        ]
        row = enrich_order_flow([sample], trades, 5_000)[0]
        self.assertEqual(row["trade_count"], 2)
        self.assertAlmostEqual(row["flow_imbalance"], -1 / 3)
        self.assertEqual(row["signed_notional"], -100)


if __name__ == "__main__":
    unittest.main()
