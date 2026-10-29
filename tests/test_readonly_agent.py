"""Unit tests for the safe portfolio snapshot; no network or credentials are used."""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from readonly_agent import build_snapshot, json_safe, position_snapshot


class ReadOnlyAgentTests(unittest.TestCase):
    def test_decimal_is_serialized_as_string(self):
        self.assertEqual(json_safe(Decimal("12.34")), "12.34")

    def test_position_snapshot_contains_only_known_fields(self):
        position = SimpleNamespace(
            symbol="AAPL",
            quantity=2,
            purchase_price=Decimal("100"),
            market_value=Decimal("220"),
            unexpected_private_field="should not be included",
        )
        result = position_snapshot(position)
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["quantity"], 2)
        self.assertNotIn("unexpected_private_field", result)

    def test_snapshot_is_explicitly_read_only(self):
        portfolio = SimpleNamespace(
            game_name="Test Game",
            portfolio_id="123",
            account_value=Decimal("1000"),
            cash=Decimal("250"),
            buying_power=Decimal("500"),
            annual_return_pct=Decimal("2.5"),
            stock_portfolio=[],
            short_portfolio=[],
            option_portfolio=[],
            open_orders=[],
        )
        snapshot = build_snapshot(SimpleNamespace(portfolio=portfolio))
        self.assertEqual(snapshot["mode"], "READ_ONLY")
        self.assertTrue(snapshot["safety"]["read_only"])
        self.assertEqual(snapshot["safety"]["orders_submitted"], 0)
        self.assertEqual(snapshot["safety"]["orders_cancelled"], 0)
        self.assertEqual(snapshot["positions"]["long"], [])


if __name__ == "__main__":
    unittest.main()
