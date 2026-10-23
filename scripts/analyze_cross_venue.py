from __future__ import annotations

import argparse
import json

from hft_lab.cross_venue import (
    basis_adjusted_displacements,
    displacement_features,
    label_hyperliquid_forward_returns,
    parse_binance_quotes,
    parse_hyperliquid_bbo_receipts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture")
    parser.add_argument("--minimum-residual-bps", type=float, default=1.0)
    args = parser.parse_args()
    hyperliquid = parse_hyperliquid_bbo_receipts(args.capture)
    reference = parse_binance_quotes(args.capture)
    raw = displacement_features(hyperliquid, reference)
    adjusted = basis_adjusted_displacements(raw)
    labelled = label_hyperliquid_forward_returns(adjusted, hyperliquid)
    output: dict[str, float | int | None] = {
        "hyperliquid_bbo": len(hyperliquid),
        "binance_quotes": len(reference),
        "causal_matches": len(raw),
        "basis_adjusted_samples": len(adjusted),
        "minimum_absolute_residual_bps": args.minimum_residual_bps,
    }
    for horizon in (1_000, 5_000, 30_000):
        key = f"forward_{horizon}ms_bps"
        eligible = [
            row for row in labelled
            if row[key] is not None and abs(float(row["basis_residual_bps"])) >= args.minimum_residual_bps
        ]
        signed = [
            (1 if float(row["basis_residual_bps"]) > 0 else -1) * float(row[key])
            for row in eligible
        ]
        output[f"n_{horizon}ms"] = len(signed)
        output[f"mean_signed_{horizon}ms_bps"] = sum(signed) / len(signed) if signed else None
        output[f"hit_rate_{horizon}ms"] = sum(value > 0 for value in signed) / len(signed) if signed else None
        output[f"gross_moves_over_9bps_{horizon}ms"] = sum(value > 9 for value in signed)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
