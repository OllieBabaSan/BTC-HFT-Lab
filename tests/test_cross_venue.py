from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hft_lab.cross_venue import (
    ReferenceQuote,
    basis_adjusted_displacements,
    displacement_features,
    label_hyperliquid_forward_returns,
    parse_binance_quotes,
    parse_hyperliquid_bbo_receipts,
)
from hft_lab.features import BookFeatures


class CrossVenueTests(unittest.TestCase):
    def test_parses_valid_binance_book_ticker(self) -> None:
        records = [
            {"venue": "binance", "channel": "bookTicker", "receivedAtMs": 1001,
             "payload": {"E": 1000, "b": "99", "a": "101"}},
            {"venue": "hyperliquid", "channel": "bbo", "receivedAtMs": 1002, "payload": {}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
            quotes = parse_binance_quotes(path)
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].midpoint, 100.0)
        self.assertEqual(quotes[0].exchange_time_ms, 1000)

    def test_join_is_causal_and_rejects_stale_reference(self) -> None:
        reference = [
            ReferenceQuote(900, 890, 100, 102),
            ReferenceQuote(1_100, 1_090, 109, 111),
        ]
        samples = [
            BookFeatures(1_000, 100, 1, 100, 0, 0, 0, "bbo"),
            BookFeatures(3_000, 100, 1, 100, 0, 0, 0, "bbo"),
        ]
        rows = displacement_features(samples, reference, max_reference_age_ms=500)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["reference_age_ms"], 100)
        self.assertAlmostEqual(rows[0]["displacement_bps"], 100.0)

    def test_hyperliquid_join_timestamp_is_local_receipt_time(self) -> None:
        record = {
            "venue": "hyperliquid", "channel": "bbo", "receivedAtMs": 2_000,
            "payload": {"channel": "bbo", "data": {"time": 1_500,
                "bbo": [{"px": "99", "sz": "2"}, {"px": "101", "sz": "1"}]}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(json.dumps(record), encoding="utf-8")
            samples = parse_hyperliquid_bbo_receipts(path)
        self.assertEqual(samples[0].timestamp_ms, 2_000)

    def test_basis_uses_only_prior_rows(self) -> None:
        rows = [
            {"timestamp_ms": 1_000, "displacement_bps": 5.0},
            {"timestamp_ms": 2_000, "displacement_bps": 7.0},
            {"timestamp_ms": 3_000, "displacement_bps": 20.0},
        ]
        adjusted = basis_adjusted_displacements(rows, lookback_ms=10_000, minimum_history=2)
        self.assertEqual(len(adjusted), 1)
        self.assertEqual(adjusted[0]["basis_baseline_bps"], 6.0)
        self.assertEqual(adjusted[0]["basis_residual_bps"], 14.0)

    def test_forward_label_rejects_capture_gap(self) -> None:
        samples = [
            BookFeatures(1_000, 100, 1, 100, 0, 0, 0, "bbo"),
            BookFeatures(10_000, 110, 1, 110, 0, 0, 0, "bbo"),
        ]
        rows = [{"timestamp_ms": 1_000, "displacement_bps": 1.0}]
        labelled = label_hyperliquid_forward_returns(rows, samples, (1_000,), max_lateness_ms=500)
        self.assertIsNone(labelled[0]["forward_1000ms_bps"])


if __name__ == "__main__":
    unittest.main()
