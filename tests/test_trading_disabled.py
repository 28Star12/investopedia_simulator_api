"""Tests that transaction submission and cancellation remain disabled."""
import unittest
from unittest.mock import Mock

from safety_policy import (
    TRADING_ENABLED,
    TradingDisabledError,
    require_trading_enabled,
)
from trade_common import Trade, PreparedTrade


class TradingDisabledTests(unittest.TestCase):
    def test_trading_is_disabled_by_default(self):
        self.assertFalse(TRADING_ENABLED)

    def test_policy_rejects_any_mutating_action(self):
        for action in ("buy", "sell", "option trade", "order cancellation"):
            with self.subTest(action=action):
                with self.assertRaises(TradingDisabledError):
                    require_trading_enabled(action)

    def test_trade_execute_is_blocked_before_network_access(self):
        trade = Trade("portfolio", "AAPL", 1, "BUY")
        trade._validated = True
        with self.assertRaises(TradingDisabledError):
            trade.execute()

    def test_prepared_trade_execute_is_blocked_before_network_access(self):
        prepared = PreparedTrade("https://example.invalid", {})
        with self.assertRaises(TradingDisabledError):
            prepared.execute()

    def test_policy_error_says_no_order_was_sent(self):
        with self.assertRaisesRegex(TradingDisabledError, "No order was sent"):
            require_trading_enabled("test action")


if __name__ == "__main__":
    unittest.main()
