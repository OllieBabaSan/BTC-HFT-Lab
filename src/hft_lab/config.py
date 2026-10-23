from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class HftConfig:
    initial_equity: float = 1_000.0
    max_inventory_notional: float = 250.0
    max_leverage: float = 3.0
    max_loss_per_position: float = 5.0
    maker_fee: float = 0.00015
    taker_fee: float = 0.00045
    assumed_latency_ms: int = 250
    stale_after_ms: int = 1_500
    minimum_notional: float = 10.0
    minimum_edge_bps: float = 5.0

    @classmethod
    def from_json(cls, path: str | Path) -> "HftConfig":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

