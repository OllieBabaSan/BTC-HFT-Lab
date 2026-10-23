from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from hft_lab.ingest import parse_raw_events, summarize_capture
from hft_lab.labels import label_forward_returns


class IngestTests(unittest.TestCase):
    def test_parses_book_and_trade_messages(self) -> None:
        events = [
            {"receivedAtMs": 1, "payload": {"channel": "l2Book", "data": {"time": 1, "levels": [[{"px": "99", "sz": "2"}], [{"px": "101", "sz": "1"}]]}}},
            {"receivedAtMs": 2, "payload": {"channel": "trades", "data": [{"time": 2, "px": "100", "sz": "0.1", "side": "B"}]}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "events.jsonl"
            capture.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            books, trades = parse_raw_events(capture)
            self.assertEqual(len(books), 1)
            self.assertEqual(len(trades), 1)
            self.assertEqual(trades[0].aggressor, 1)
            self.assertGreater(summarize_capture(capture)["median_spread_bps"], 0)

    def test_forward_labels_use_first_observation_at_or_after_horizon(self) -> None:
        events = [
            {"receivedAtMs": time, "payload": {"channel": "bbo", "data": {"time": time, "bbo": [{"px": str(price - 1), "sz": "1"}, {"px": str(price + 1), "sz": "1"}]}}}
            for time, price in ((1_000, 100), (2_500, 101), (7_000, 102))
        ]
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "events.jsonl"
            capture.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            books, _ = parse_raw_events(capture)
            labels = label_forward_returns(books, (1_000,))
            self.assertAlmostEqual(labels[0]["forward_1000ms_bps"], 100.0)
            self.assertIsNone(labels[-1]["forward_1000ms_bps"])

    def test_forward_label_does_not_cross_capture_gap(self) -> None:
        events = [
            {"receivedAtMs": time, "payload": {"channel": "bbo", "data": {"time": time, "bbo": [{"px": "99", "sz": "1"}, {"px": "101", "sz": "1"}]}}}
            for time in (1_000, 10_000)
        ]
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "events.jsonl"
            capture.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            books, _ = parse_raw_events(capture)
            self.assertIsNone(label_forward_returns(books, (1_000,), max_lateness_ms=500)[0]["forward_1000ms_bps"])

    def test_capture_summary_excludes_inter_session_gaps(self) -> None:
        events = [
            {"receivedAtMs": time, "payload": {"channel": "bbo", "data": {"time": time, "bbo": [{"px": "99", "sz": "1"}, {"px": "101", "sz": "1"}]}}}
            for time in (1_000, 2_000, 102_000, 104_000)
        ]
        with tempfile.TemporaryDirectory() as directory:
            capture = Path(directory) / "events.jsonl"
            capture.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            summary = summarize_capture(capture, session_gap_ms=10_000)
            self.assertEqual(summary["sessions"], 2)
            self.assertEqual(summary["active_duration_seconds"], 3.0)
            self.assertEqual(summary["wall_duration_seconds"], 103.0)
            self.assertEqual(summary["bbo_updates"], 4)
            self.assertEqual(summary["l2_updates"], 0)


if __name__ == "__main__":
    unittest.main()
