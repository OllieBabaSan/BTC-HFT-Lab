from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from hft_lab.ingest import parse_raw_events, summarize_capture
from hft_lab.screening import screen_order_flow


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    parser.add_argument("--minimum-imbalance", type=float, default=0.5)
    args = parser.parse_args()
    books, trades = parse_raw_events(args.capture)
    results = [
        asdict(screen_order_flow(
            books, trades, horizon,
            minimum_absolute_imbalance=args.minimum_imbalance,
        ))
        for horizon in (1_000, 5_000, 30_000)
    ]
    print(json.dumps({"capture": summarize_capture(args.capture), "screens": results}, indent=2))


if __name__ == "__main__":
    main()
