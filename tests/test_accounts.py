from __future__ import annotations

import unittest

from hft_lab.accounts import independent_candidate_accounts
from hft_lab.config import HftConfig
from hft_lab.validation import GoNoGoEvidence, go_no_go


class AccountTests(unittest.TestCase):
    def test_candidates_have_isolated_equity(self) -> None:
        config = HftConfig()
        accounts = independent_candidate_accounts(config)
        external = accounts["external_price_displacement"]
        self.assertTrue(external.open_position(1, 100, 100, 98, config.taker_fee, config))
        self.assertTrue(external.close_position(101, config.taker_fee))
        self.assertEqual(accounts["passive_market_making"].equity, 1_000)
        self.assertEqual(accounts["order_flow_momentum"].equity, 1_000)
        self.assertAlmostEqual(external.equity, 1_000.91)

    def test_inventory_and_planned_loss_caps_are_enforced(self) -> None:
        config = HftConfig()
        account = independent_candidate_accounts(config)["order_flow_momentum"]
        self.assertFalse(account.open_position(1, 251, 100, 99, config.taker_fee, config))
        self.assertFalse(account.open_position(1, 250, 100, 97, config.taker_fee, config))
        self.assertEqual(account.equity, 1_000)

    def test_go_gate_requires_sufficient_clean_oos_evidence(self) -> None:
        weak = GoNoGoEvidence(1, 10, 1, 1.1, -0.02, 0)
        self.assertFalse(go_no_go(weak)[0])
        strong = GoNoGoEvidence(5, 100, 10, 1.3, -0.05, 0)
        self.assertTrue(go_no_go(strong)[0])

    def test_funding_debits_longs_and_credits_shorts(self) -> None:
        config = HftConfig()
        accounts = independent_candidate_accounts(config)
        long_account = accounts["external_price_displacement"]
        short_account = accounts["order_flow_momentum"]
        self.assertTrue(long_account.open_position(1, 100, 100, 98, config.maker_fee, config))
        self.assertTrue(short_account.open_position(-1, 100, 100, 102, config.maker_fee, config))
        self.assertAlmostEqual(long_account.apply_funding(0.0001), 0.01)
        self.assertAlmostEqual(short_account.apply_funding(0.0001), -0.01)
        self.assertLess(long_account.equity, short_account.equity)


if __name__ == "__main__":
    unittest.main()
