from __future__ import annotations

from bisect import bisect_left
from dataclasses import asdict

from .features import BookFeatures


def label_forward_returns(
    samples: list[BookFeatures],
    horizons_ms: tuple[int, ...] = (1_000, 5_000, 30_000),
    max_lateness_ms: int = 1_000,
) -> list[dict[str, float | int | str | None]]:
    ordered = sorted(samples, key=lambda sample: sample.timestamp_ms)
    timestamps = [sample.timestamp_ms for sample in ordered]
    rows: list[dict[str, float | int | str | None]] = []
    for sample in ordered:
        row: dict[str, float | int | str | None] = asdict(sample)
        for horizon in horizons_ms:
            future_index = bisect_left(timestamps, sample.timestamp_ms + horizon)
            key = f"forward_{horizon}ms_bps"
            if future_index >= len(ordered) or timestamps[future_index] > sample.timestamp_ms + horizon + max_lateness_ms:
                row[key] = None
            else:
                row[key] = (ordered[future_index].midpoint - sample.midpoint) / sample.midpoint * 10_000
        rows.append(row)
    return rows
