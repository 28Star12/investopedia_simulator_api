"""Tests for detecting suspicious portfolio-history data."""
import unittest

from portfolio_analysis import analyze_snapshot


class PortfolioHistoryQualityTests(unittest.TestCase):
    def test_flags_repeated_zero_history_before_positive_latest_value(self):
        report = analyze_snapshot({
            "account": {"account_value": "100000", "cash": "100000"},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {"equity": [0, 0, 0, 100000]},
        })

        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("HISTORY_MAY_BE_INCOMPLETE", codes)

    def test_does_not_flag_positive_history(self):
        report = analyze_snapshot({
            "account": {"account_value": "10200", "cash": "5000"},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {"equity": [10000, 10100, 10200]},
        })

        codes = {flag["code"] for flag in report["flags"]}
        self.assertNotIn("HISTORY_MAY_BE_INCOMPLETE", codes)

    def test_ignores_history_without_enough_numeric_values(self):
        report = analyze_snapshot({
            "account": {"account_value": "100000", "cash": "100000"},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {"equity": [0, None, "not available", 100000]},
        })

        codes = {flag["code"] for flag in report["flags"]}
        self.assertNotIn("HISTORY_MAY_BE_INCOMPLETE", codes)


if __name__ == "__main__":
    unittest.main()
