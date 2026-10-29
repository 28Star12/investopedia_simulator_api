"""Tests for portfolio-history quality and performance diagnostics."""
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
        self.assertFalse(report["portfolio_performance"]["available"])
        self.assertIsNotNone(report["portfolio_performance"]["limitation"])

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

    def test_calculates_return_from_alpaca_base_value(self):
        report = analyze_snapshot({
            "account": {"account_value": "12000", "cash": "2000"},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {
                "base_value": "10000",
                "equity": [10500, 11000, 12000],
                "timeframe": "1D",
            },
        })

        performance = report["portfolio_performance"]
        self.assertTrue(performance["available"])
        self.assertEqual(performance["starting_value"], "10000.00")
        self.assertEqual(performance["ending_value"], "12000.00")
        self.assertEqual(performance["absolute_change"], "2000.00")
        self.assertEqual(performance["return_pct"], "20.00")
        self.assertEqual(performance["baseline"], "base_value")

    def test_uses_first_equity_when_base_value_is_unavailable(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {"equity": [20000, 19000]},
        })

        performance = report["portfolio_performance"]
        self.assertTrue(performance["available"])
        self.assertEqual(performance["return_pct"], "-5.00")
        self.assertEqual(performance["baseline"], "first_equity_observation")

    def test_requires_two_valid_equity_observations(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {"equity": [None, "bad", 10000]},
        })

        performance = report["portfolio_performance"]
        self.assertFalse(performance["available"])
        self.assertIsNone(performance["return_pct"])


class PortfolioExposureTests(unittest.TestCase):
    def _report(self, long_positions, short_positions=None, account_value="1000"):
        return analyze_snapshot({
            "account": {"account_value": account_value, "cash": "100"},
            "positions": {
                "long": long_positions,
                "short": short_positions or [],
                "options": [],
            },
        })

    def test_reports_long_short_gross_and_net_exposure(self):
        report = self._report(
            [{"symbol": "AAA", "market_value": "600"}],
            [{"symbol": "BBB", "market_value": "-200"}],
        )
        exposure = report["exposure_summary"]
        self.assertEqual(exposure["long_gross_market_value"], "600.00")
        self.assertEqual(exposure["short_gross_market_value"], "200.00")
        self.assertEqual(exposure["stock_gross_market_value"], "800.00")
        self.assertEqual(exposure["stock_net_exposure"], "400.00")
        self.assertEqual(exposure["long_share_of_stock_gross_pct"], "75.00")
        self.assertEqual(exposure["short_share_of_stock_gross_pct"], "25.00")

    def test_flags_concentration_at_fifty_percent(self):
        report = self._report([
            {"symbol": "AAA", "market_value": "500"},
            {"symbol": "BBB", "market_value": "300"},
            {"symbol": "CCC", "market_value": "200"},
        ])
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("HIGH_POSITION_CONCENTRATION", codes)
        self.assertNotIn("ELEVATED_POSITION_CONCENTRATION", codes)

    def test_flags_elevated_concentration_from_twenty_five_to_under_fifty(self):
        report = self._report([
            {"symbol": "AAA", "market_value": "400"},
            {"symbol": "BBB", "market_value": "350"},
            {"symbol": "CCC", "market_value": "250"},
        ])
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("ELEVATED_POSITION_CONCENTRATION", codes)
        self.assertNotIn("HIGH_POSITION_CONCENTRATION", codes)

    def test_does_not_flag_concentration_below_twenty_five_percent(self):
        report = self._report([
            {"symbol": "AAA", "market_value": "200"},
            {"symbol": "BBB", "market_value": "200"},
            {"symbol": "CCC", "market_value": "200"},
            {"symbol": "DDD", "market_value": "200"},
            {"symbol": "EEE", "market_value": "200"},
        ])
        codes = {flag["code"] for flag in report["flags"]}
        self.assertNotIn("ELEVATED_POSITION_CONCENTRATION", codes)
        self.assertNotIn("HIGH_POSITION_CONCENTRATION", codes)

    def test_missing_market_value_is_excluded_and_reported(self):
        report = self._report([
            {"symbol": "AAA", "market_value": "500"},
            {"symbol": "BBB", "market_value": None},
        ])
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("INCOMPLETE_POSITION_VALUES", codes)
        self.assertEqual(report["largest_exposures"][0]["symbol"], "AAA")

    def test_zero_account_value_does_not_create_exposure_percentages(self):
        report = self._report(
            [{"symbol": "AAA", "market_value": "500"}],
            account_value="0",
        )
        exposure = report["exposure_summary"]
        self.assertIsNone(exposure["stock_gross_as_pct_of_account_value"])
        self.assertIsNone(exposure["net_stock_exposure_as_pct_of_account_value"])


    def test_combines_same_symbol_absolute_exposure_across_sides(self):
        report = self._report(
            [{"symbol": "XYZ", "market_value": "300"}],
            [{"symbol": "XYZ", "market_value": "-200"}],
        )
        xyz = next(item for item in report["largest_exposures"] if item["symbol"] == "XYZ")
        self.assertEqual(xyz["absolute_market_value"], "500.00")
        self.assertEqual(xyz["share_of_tracked_positions_pct"], "100.00")

    def test_options_are_reported_separately_from_stock_net_exposure(self):
        report = analyze_snapshot({
            "account": {"account_value": "1000"},
            "positions": {
                "long": [{"symbol": "AAA", "market_value": "300"}],
                "short": [{"symbol": "BBB", "market_value": "-100"}],
                "options": [{"symbol": "AAA_CALL", "underlying_symbol": "AAA", "market_value": "50"}],
            },
        })
        exposure = report["exposure_summary"]
        self.assertEqual(exposure["options_gross_market_value"], "50.00")
        self.assertEqual(exposure["stock_net_exposure"], "200.00")
        self.assertEqual(exposure["stock_gross_market_value"], "400.00")



class UnrealizedProfitLossTests(unittest.TestCase):
    def test_sums_unrealized_pl_and_breaks_it_down_by_position_category(self):
        report = analyze_snapshot({
            "account": {"account_value": "10000"},
            "positions": {
                "long": [{"symbol": "AAA", "market_value": "1200", "unrealized_pl": "200"}],
                "short": [{"symbol": "BBB", "market_value": "-500", "unrealized_pl": "-50"}],
                "options": [{"symbol": "CCC", "market_value": "300", "unrealized_pl": "25"}],
                "other": [{"symbol": "DDD", "market_value": "100", "unrealized_pl": "-5"}],
            },
        })

        pnl = report["open_positions_unrealized_pl"]
        self.assertTrue(pnl["available"])
        self.assertEqual(pnl["total"], "170.00")
        self.assertEqual(pnl["by_category"]["long"], "200.00")
        self.assertEqual(pnl["by_category"]["short"], "-50.00")
        self.assertEqual(pnl["by_category"]["options"], "25.00")
        self.assertEqual(pnl["by_category"]["other"], "-5.00")
        self.assertEqual(pnl["positions_with_data"], 4)

    def test_marks_unrealized_pl_incomplete_when_a_position_value_is_missing(self):
        report = analyze_snapshot({
            "account": {"account_value": "10000"},
            "positions": {
                "long": [
                    {"symbol": "AAA", "market_value": "100", "unrealized_pl": "10"},
                    {"symbol": "BBB", "market_value": "200"},
                ],
                "short": [], "options": [],
            },
        })

        pnl = report["open_positions_unrealized_pl"]
        self.assertEqual(pnl["total"], "10.00")
        self.assertEqual(pnl["positions_missing_data"], 1)
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("INCOMPLETE_UNREALIZED_PNL", codes)

    def test_unrealized_pl_is_unavailable_when_no_positions_have_values(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {"long": [{"symbol": "AAA"}], "short": [], "options": []},
        })

        pnl = report["open_positions_unrealized_pl"]
        self.assertFalse(pnl["available"])
        self.assertIsNone(pnl["total"])
        self.assertEqual(pnl["positions_with_data"], 0)
        self.assertEqual(pnl["positions_missing_data"], 1)


class IntradayProfitLossTests(unittest.TestCase):
    def test_sums_intraday_pl_by_category(self):
        report = analyze_snapshot({
            "account": {"account_value": "10000"},
            "positions": {
                "long": [{"symbol": "AAA", "unrealized_intraday_pl": "30"}],
                "short": [{"symbol": "BBB", "unrealized_intraday_pl": "-10"}],
                "options": [{"symbol": "CCC", "unrealized_intraday_pl": "5"}],
                "other": [{"symbol": "DDD", "unrealized_intraday_pl": "-2"}],
            },
        })

        pnl = report["open_positions_intraday_pl"]
        self.assertTrue(pnl["available"])
        self.assertEqual(pnl["total"], "23.00")
        self.assertEqual(pnl["by_category"]["long"], "30.00")
        self.assertEqual(pnl["by_category"]["short"], "-10.00")
        self.assertEqual(pnl["by_category"]["options"], "5.00")
        self.assertEqual(pnl["by_category"]["other"], "-2.00")

    def test_marks_intraday_pl_incomplete_when_values_are_missing(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {
                "long": [{"symbol": "AAA", "unrealized_intraday_pl": "4"}, {"symbol": "BBB"}],
                "short": [], "options": [],
            },
        })

        pnl = report["open_positions_intraday_pl"]
        self.assertEqual(pnl["total"], "4.00")
        self.assertEqual(pnl["positions_missing_data"], 1)
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("INCOMPLETE_INTRADAY_PNL", codes)



class HistoryTimestampOrderTests(unittest.TestCase):
    def test_flags_out_of_order_numeric_timestamps(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {
                "timestamp": [100, 300, 200, 400],
                "equity": ["1000", "1010", "1005", "1020"],
            },
        })

        quality = report["portfolio_history_data_quality"]
        self.assertEqual(quality["out_of_order_timestamp_pairs"], 1)
        codes = {flag["code"] for flag in report["flags"]}
        self.assertIn("OUT_OF_ORDER_HISTORY_TIMESTAMPS", codes)


class HistoryPerformanceReliabilityTests(unittest.TestCase):
    def test_does_not_calculate_return_when_history_series_lengths_mismatch(self):
        report = analyze_snapshot({
            "account": {},
            "positions": {"long": [], "short": [], "options": []},
            "portfolio_history": {
                "timestamp": [100, 200, 300],
                "equity": ["10000", "10500"],
                "base_value": "10000",
                "timeframe": "1D",
            },
        })

        performance = report["portfolio_performance"]
        self.assertFalse(performance["available"])
        self.assertIsNone(performance["return_pct"])
        self.assertIn("inconsistent", performance["limitation"])


if __name__ == "__main__":
    unittest.main()
