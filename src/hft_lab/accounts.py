from __future__ import annotations

from dataclasses import dataclass, field

from .config import HftConfig


CANDIDATES = (
    "passive_market_making",
    "order_flow_momentum",
    "external_price_displacement",
)


@dataclass
class CandidateAccount:
    name: str
    equity: float
    peak_equity: float
    signed_notional: float = 0.0
    entry_price: float | None = None
    fees_paid: float = 0.0
    funding_paid: float = 0.0
    realized_pnl: float = 0.0
    fills: int = 0
    rejections: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> bool:
        self.rejections[reason] = self.rejections.get(reason, 0) + 1
        return False

    def open_position(
        self,
        side: int,
        notional: float,
        entry_price: float,
        stop_price: float,
        fee_rate: float,
        config: HftConfig,
    ) -> bool:
        if self.signed_notional:
            return self.reject("position already open")
        if side not in (-1, 1) or entry_price <= 0 or stop_price <= 0:
            return self.reject("invalid order")
        if notional < config.minimum_notional:
            return self.reject("below venue minimum")
        if notional > config.max_inventory_notional:
            return self.reject("inventory cap")
        if notional > self.equity * config.max_leverage:
            return self.reject("leverage ceiling")
        planned_loss = notional * abs(entry_price - stop_price) / entry_price
        if planned_loss > config.max_loss_per_position:
            return self.reject("planned loss cap")
        fee = notional * fee_rate
        self.equity -= fee
        self.fees_paid += fee
        self.signed_notional = side * notional
        self.entry_price = entry_price
        self.fills += 1
        return True

    def close_position(self, exit_price: float, fee_rate: float) -> bool:
        if not self.signed_notional or self.entry_price is None or exit_price <= 0:
            return self.reject("no open position")
        side = 1 if self.signed_notional > 0 else -1
        notional = abs(self.signed_notional)
        pnl = side * notional * (exit_price - self.entry_price) / self.entry_price
        fee = notional * fee_rate
        self.equity += pnl - fee
        self.realized_pnl += pnl
        self.fees_paid += fee
        self.peak_equity = max(self.peak_equity, self.equity)
        self.signed_notional = 0.0
        self.entry_price = None
        self.fills += 1
        return True

    def apply_funding(self, funding_rate: float) -> float:
        """Positive funding is paid by longs and received by shorts."""
        payment = self.signed_notional * funding_rate
        self.equity -= payment
        self.funding_paid += payment
        return payment

    @property
    def drawdown(self) -> float:
        return self.equity / self.peak_equity - 1 if self.peak_equity else 0.0


def independent_candidate_accounts(config: HftConfig) -> dict[str, CandidateAccount]:
    return {
        name: CandidateAccount(name=name, equity=config.initial_equity, peak_equity=config.initial_equity)
        for name in CANDIDATES
    }
