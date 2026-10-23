from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .models import Book, TradePrint


class JsonlRecorder:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def record_book(self, book: Book) -> None:
        book.validate()
        payload = {
            "timestamp_ms": book.timestamp_ms,
            "bids": [asdict(level) for level in book.bids],
            "asks": [asdict(level) for level in book.asks],
        }
        self._append("books.jsonl", payload)

    def record_trade(self, trade: TradePrint) -> None:
        if trade.aggressor not in (-1, 1) or trade.price <= 0 or trade.size <= 0:
            raise ValueError("Invalid trade print")
        self._append("trades.jsonl", asdict(trade))

    def _append(self, name: str, payload: dict) -> None:
        with (self.directory / name).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, separators=(",", ":")) + "\n")

