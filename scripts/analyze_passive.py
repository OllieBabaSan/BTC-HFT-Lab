from __future__ import annotations

from dataclasses import asdict
import json

from hft_lab.config import HftConfig
from hft_lab.ingest import parse_l2_books, parse_raw_events
from hft_lab.passive_screening import screen_passive_quotes


def main() -> None:
    path = "data/raw_events.jsonl"
    books = parse_l2_books(path)
    features, trades = parse_raw_events(path)
    bbo = [sample for sample in features if sample.source == "bbo"]
    results = {
        str(multiplier): asdict(screen_passive_quotes(
            books, bbo, trades, HftConfig(), queue_multiplier=multiplier,
        ))
        for multiplier in (0.0, 0.5, 1.0, 2.0)
    }
    print(json.dumps({"l2_snapshots": len(books), "queue_scenarios": results}, indent=2))


if __name__ == "__main__":
    main()
