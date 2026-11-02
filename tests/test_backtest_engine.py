import unittest
from backtest_engine import run_backtest

class BacktestTests(unittest.TestCase):
    def test_candidate_uses_only_post_signal_prices(self):
        bars={"AAA":[{"t":"2024-01-01T00:00:00Z","c":10},{"t":"2024-01-02T00:00:00Z","c":11},{"t":"2024-01-03T00:00:00Z","c":12}]}
        snaps=[{"symbol":"AAA","observed_at":"2024-01-01T12:00:00Z","investment_review":{"decision":"CANDIDATE"}}]
        r=run_backtest(bars,snaps,1000,0)
        self.assertEqual(r["status"],"OK")
        self.assertAlmostEqual(r["metrics"]["total_return_pct"],9.091,places=2)
    def test_watch_stays_cash(self):
        bars={"AAA":[{"t":"2024-01-01T00:00:00Z","c":10},{"t":"2024-01-02T00:00:00Z","c":20}]}
        snaps=[{"symbol":"AAA","observed_at":"2023-12-31T00:00:00Z","investment_review":{"decision":"WATCH"}}]
        r=run_backtest(bars,snaps,1000,0)
        self.assertEqual(r["metrics"]["total_return_pct"],0)
    def test_benchmark_is_clipped_to_portfolio_window(self):\n        bars={"AAA":[{"t":"2024-01-02T00:00:00Z","c":10},{"t":"2024-01-03T00:00:00Z","c":11}]}\n        snaps=[{"symbol":"AAA","observed_at":"2024-01-01T00:00:00Z","investment_review":{"decision":"CANDIDATE"}}]\n        spy=[{"t":"2023-12-01T00:00:00Z","c":50},{"t":"2024-01-02T00:00:00Z","c":100},{"t":"2024-01-03T00:00:00Z","c":110},{"t":"2024-02-01T00:00:00Z","c":200}]\n        r=run_backtest(bars,snaps,1000,0,spy)\n        self.assertAlmostEqual(r["metrics"]["benchmark_return_pct"],10,places=2)\n    def test_empty_bars(self):
        self.assertEqual(run_backtest({},[])["status"],"NO_PRICE_DATA")
if __name__=="__main__": unittest.main()
