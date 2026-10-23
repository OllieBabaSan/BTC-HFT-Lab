# BTC HFT Lab

Independent event-driven research project for BTC perpetual microstructure on
Hyperliquid. It does not import the BTC TA Lab, legacy MockingBot, or Discord
signals system.

## Candidate strategies

1. Selective passive market making
2. Short-horizon order-flow momentum
3. External-venue price displacement

All three share only infrastructure and receive separate virtual accounts.
The account ledger enforces independent equity, the 250 USDC inventory ceiling,
the 5 USDC planned-loss ceiling, and leverage before accepting any simulated entry.
Passive execution preserves partial fills after estimated queue depletion, cancels
the unfilled remainder at expiry, and charges maker fees only on executed notional.
Open virtual positions accrue signed funding payments.
Every passive fill can be marked against a later midpoint to measure signed markout
and adverse selection. A dead-man gate blocks activity and records a safety violation
if any strategy-required feed is disconnected or older than the stale-data threshold.

## Initial safety mandate

- 1,000 USDC virtual equity per candidate
- 250 USDC maximum inventory notional
- 5 USDC maximum planned position loss
- 3x absolute leverage ceiling
- No credentials or live-order implementation
- Base-tier fees; no maker rebate assumption
- Stale data disables quoting

## Current milestone

The recorder schema, order-book feature calculations, edge gate, and conservative
maker-fill simulator are implemented with deterministic tests. Live public stream
collection and external reference data are the next milestone.

## Public capture

The recorder uses the bundled runtime's native WebSocket support and requires no
API key:

```powershell
node scripts/collect_hyperliquid.mjs 60 data/raw_events.jsonl
```

It subscribes only to public BTC L2-book, best-bid/offer, and trade channels and stores raw messages
with local receipt timestamps for later latency and feature analysis.

Trailing aggressive buy/sell notional, flow imbalance, trade count, and realized
trade volatility can be joined to each BBO observation without using future data.
The order-flow screen selects sufficiently one-sided trailing flow and enforces a
full-horizon cooldown between observations, avoiding inflated results from many
overlapping BBO updates that describe the same price move.
Capture summaries split recordings at gaps longer than ten seconds, reporting active
recording time separately from wall-clock span so disconnected sessions do not dilute
event-rate and label-coverage audits.

For the external-displacement candidate, `scripts/collect_cross_venue.mjs` records
Hyperliquid L2/BBO/trades and Binance BTCUSDT best quotes into one append-only stream with
local receipt timestamps. The causal join uses only a Binance quote already received
when the Hyperliquid observation arrives and rejects stale reference quotes.
The strategy feature subtracts a trailing median basis built strictly from earlier
matches, requires a minimum history, and attaches gap-safe future Hyperliquid returns.
Hybrid eligibility additionally requires cross-venue residual, signed flow, depth
depletion, and current depth imbalance to agree directionally while short-horizon
trade volatility remains inside a configured safety band.

No candidate can pass the research gate without at least five out-of-sample sessions,
100 completed round trips, positive net PnL after all modeled costs, profit factor of
at least 1.2, drawdown no worse than 10%, and zero stale-data or safety violations.

The passive screen quotes both sides at the visible inside price, applies latency,
depletes a configurable fraction of visible queue before our order, preserves partial
fills, and measures five-second markout. Continuous inside-spread market making is
rejected on the initial sample even under the impossible zero-queue upper bound.
