"""Unit tests for the safe portfolio snapshot; no network or credentials are used."""
import unittest
from decimal import Decimal
from types import SimpleNamespace

from readonly_agent import build_snapshot, json_safe, position_snapshot
from portfolio_analysis import analyze_snapshot


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

    def test_analysis_flags_short_positions_and_reports_cash_ratio(self):
        snapshot = {
            "account": {"account_value": "1000", "cash": "250"},
            "positions": {
                "long": [{"symbol": "AAPL", "market_value": "300"}],
                "short": [{"symbol": "TSLA", "market_value": "-100"}],
                "options": [],
            },
        }
        result = analyze_snapshot(snapshot)
        self.assertEqual(result["cash_as_pct_of_account_value"], "25.00")
        self.assertEqual(result["position_count"], 2)
        self.assertIn("SHORT_EXPOSURE", [flag["code"] for flag in result["flags"]])
        self.assertTrue(result["not_financial_advice"])

    def test_analysis_handles_missing_values(self):
        result = analyze_snapshot({
            "account": {"account_value": None, "cash": None},
            "positions": {"long": [{"symbol": "XYZ"}], "short": [], "options": []},
        })
        self.assertIsNone(result["cash_as_pct_of_account_value"])
        self.assertIn(
            "INCOMPLETE_POSITION_VALUES",
            [flag["code"] for flag in result["flags"]],
        )

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
