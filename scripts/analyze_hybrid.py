from __future__ import annotations

from dataclasses import asdict
import json

from hft_lab.cross_venue import parse_binance_quotes, parse_hyperliquid_bbo_receipts
from hft_lab.hybrid import assemble_hybrid_rows, parse_hybrid_hyperliquid
from hft_lab.hybrid_screening import screen_hybrid


def main() -> None:
    path = "data/hybrid_events.jsonl"
    states, trades = parse_hybrid_hyperliquid(path)
    reference = parse_binance_quotes(path)
    bbo = parse_hyperliquid_bbo_receipts(path)
    sessions = []
    current = []
    for state in states:
        if current and state.features.timestamp_ms - current[-1].features.timestamp_ms > 10_000:
            sessions.append(current)
            current = []
        current.append(state)
    if current:
        sessions.append(current)
    session_results = []
    for index, session_states in enumerate(sessions, start=1):
        start, end = session_states[0].features.timestamp_ms, session_states[-1].features.timestamp_ms
        session_trades = [trade for trade in trades if start <= trade.timestamp_ms <= end]
        session_reference = [quote for quote in reference if start - 1_000 <= quote.received_at_ms <= end]
        session_bbo = [sample for sample in bbo if start <= sample.timestamp_ms <= end + 31_000]
        rows = assemble_hybrid_rows(session_states, session_trades, session_reference)
        screens = {}
        for residual in (0.25, 0.5, 1.0):
            for flow in (0.2, 0.4):
                key = f"residual_{residual}_flow_{flow}"
                screens[key] = asdict(screen_hybrid(
                    rows, session_bbo, minimum_residual_bps=residual,
                    minimum_flow_imbalance=flow,
                ))
        session_results.append({
            "session": index,
            "role": "development" if index == 1 else "held_out",
            "fully_aligned_rows": len(rows),
            "screens": screens,
        })
    print(json.dumps({
        "l2_states": len(states),
        "trades": len(trades),
        "binance_quotes": len(reference),
        "bbo_samples": len(bbo),
        "sessions": session_results,
    }, indent=2))


if __name__ == "__main__":
    main()
