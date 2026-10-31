import unittest
from technical_analysis import analyze_bars, AlpacaTechnicalAnalyzer
from unittest.mock import Mock


class FakeResponse:
    ok = True
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload


class TechnicalAnalysisTests(unittest.TestCase):
    def test_insufficient_history_is_not_scored(self):
        result = analyze_bars([{"c": 10 + i} for i in range(20)])
        self.assertEqual(result["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(result["score"])

    def test_indicators_return_bounded_score_and_both_strategy_fields(self):
        bars = [{"c": 50 + i * 0.2} for i in range(60)]
        result = analyze_bars(bars)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertIsNotNone(result["sma_20"])
        self.assertIsNotNone(result["sma_50"])
        self.assertIsNotNone(result["rsi_14"])
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 1)
        self.assertIn("status", result["reversal"])
        self.assertIn("status", result["trend"])

    def test_alpaca_bars_are_fetched_with_get_and_iex(self):
        session = Mock()
        session.get.return_value = FakeResponse({"bars": {"AAA": [{"c": 10 + i} for i in range(60)]}})
        result = AlpacaTechnicalAnalyzer("key", "secret", session).collect(["AAA"])
        self.assertEqual(result["AAA"]["status"], "AVAILABLE")
        self.assertEqual(session.get.call_args.args[0], "https://data.alpaca.markets/v2/stocks/bars")
        self.assertEqual(session.get.call_args.kwargs["params"]["feed"], "iex")
        self.assertEqual(session.get.call_args.kwargs["params"]["timeframe"], "1Day")
        self.assertEqual(session.get.call_args.kwargs["params"]["symbols"], "AAA")


if __name__ == "__main__":
    unittest.main()
