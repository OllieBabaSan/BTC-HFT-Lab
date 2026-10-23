from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hft_lab.features import BookFeatures
from hft_lab.cross_venue import ReferenceQuote
from hft_lab.hybrid import DepthState, assemble_hybrid_rows, depth_depletion, parse_hybrid_hyperliquid
from hft_lab.models import TradePrint


class HybridTests(unittest.TestCase):
    def test_joint_capture_uses_local_receipt_time(self) -> None:
        records = [
            {"venue": "hyperliquid", "channel": "l2Book", "receivedAtMs": 2_000,
             "payload": {"data": {"time": 1_000, "levels": [
                 [{"px": "99", "sz": "2"}], [{"px": "101", "sz": "1"}],
             ]}}},
            {"venue": "hyperliquid", "channel": "trades", "receivedAtMs": 2_100,
             "payload": {"data": [{"time": 1_100, "px": "100", "sz": "1", "side": "B"}]}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
            books, trades = parse_hybrid_hyperliquid(path)
        self.assertEqual(books[0].features.timestamp_ms, 2_000)
        self.assertEqual(trades[0].timestamp_ms, 2_100)

    def test_ask_depletion_is_positive_pressure(self) -> None:
        first = DepthState(BookFeatures(1_000, 100, 1, 100, 0, 0, 0, "l2Book"), 10, 10)
        second = DepthState(BookFeatures(1_500, 100, 1, 100, 0, 0, 0, "l2Book"), 10, 5)
        row = depth_depletion([first, second])[0]
        self.assertEqual(row["depletion_pressure"], 0.5)

    def test_depletion_does_not_cross_capture_gap(self) -> None:
        first = DepthState(BookFeatures(1_000, 100, 1, 100, 0, 0, 0, "l2Book"), 10, 10)
        second = DepthState(BookFeatures(20_000, 100, 1, 100, 0, 0, 0, "l2Book"), 10, 5)
        self.assertEqual(depth_depletion([first, second]), [])

    def test_hybrid_rows_require_all_causal_inputs(self) -> None:
        states = [
            DepthState(BookFeatures(time, 100, 1, 100, 0, 0, 0.2, "l2Book"), 10, ask)
            for time, ask in ((1_000, 10), (2_000, 9), (3_000, 8), (4_000, 7))
        ]
        trades = [TradePrint(time, 100, 1, 1) for time in (900, 1_900, 2_900, 3_900)]
        reference = [ReferenceQuote(time - 10, time - 20, 100, 102) for time in (1_000, 2_000, 3_000, 4_000)]
        rows = assemble_hybrid_rows(states, trades, reference, minimum_basis_history=2)
        self.assertEqual(len(rows), 2)
        self.assertIn("basis_residual_bps", rows[0])
        self.assertIn("depletion_pressure", rows[0])
        self.assertIn("trade_volatility_bps", rows[0])
