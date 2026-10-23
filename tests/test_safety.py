from __future__ import annotations

import unittest

from hft_lab.config import HftConfig
from hft_lab.safety import DeadManGate


class SafetyTests(unittest.TestCase):
    def test_all_required_feeds_must_be_connected_and_fresh(self) -> None:
        gate = DeadManGate(("hyperliquid", "binance"))
        gate.observe("hyperliquid", 1_000)
        self.assertFalse(gate.eligible(1_100, HftConfig()))
        self.assertEqual(gate.last_reason, "binance disconnected")
        gate.observe("binance", 1_050)
        self.assertTrue(gate.eligible(1_100, HftConfig()))

    def test_stale_or_disconnected_feed_blocks_action(self) -> None:
        gate = DeadManGate(("hyperliquid",))
        gate.observe("hyperliquid", 1_000)
        self.assertFalse(gate.eligible(3_000, HftConfig(stale_after_ms=1_500)))
        self.assertEqual(gate.last_reason, "hyperliquid stale")
        gate.observe("hyperliquid", 3_000)
        gate.disconnect("hyperliquid")
        self.assertFalse(gate.eligible(3_001, HftConfig()))
        self.assertEqual(gate.violations, 2)

    def test_future_receipt_timestamp_blocks_action(self) -> None:
        gate = DeadManGate(("hyperliquid",))
        gate.observe("hyperliquid", 2_000)
        self.assertFalse(gate.eligible(1_999, HftConfig()))
        self.assertEqual(gate.last_reason, "hyperliquid invalid timestamp")
