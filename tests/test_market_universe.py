import unittest
from decimal import Decimal
from unittest.mock import Mock

from market_universe import AlpacaMarketDiscovery


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
        self.ok = True
        self.status_code = 200
    def json(self):
        return self.payload


class MarketUniverseTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.discovery = AlpacaMarketDiscovery("paper-key", "paper-secret", self.session)

    def test_discovers_only_active_tradable_equities_and_excludes_etfs(self):
        self.session.get.return_value = FakeResponse([
            {"symbol": "AAA", "name": "Alpha", "exchange": "NASDAQ",
             "status": "active", "tradable": True, "class": "us_equity", "attributes": []},
            {"symbol": "BBB", "name": "Beta ETF", "exchange": "NYSE",
             "status": "active", "tradable": True, "class": "us_equity", "attributes": ["etf"]},
            {"symbol": "CCC", "name": "Closed", "exchange": "NYSE",
             "status": "inactive", "tradable": True, "class": "us_equity"},
            {"symbol": "DDD", "name": "Not tradable", "exchange": "NYSE",
             "status": "active", "tradable": False, "class": "us_equity"},
        ])
        assets = self.discovery.discover_assets()
        self.assertEqual([item["symbol"] for item in assets], ["AAA"])
        self.assertEqual(self.session.get.call_args.args[0],
                         "https://paper-api.alpaca.markets/v2/assets")

    def test_ranker_filters_illiquid_and_ranks_by_transparent_score(self):
        assets = [
            {"symbol": "AAA", "name": "Alpha", "exchange": "NASDAQ"},
            {"symbol": "BBB", "name": "Beta", "exchange": "NYSE"},
            {"symbol": "CCC", "name": "Gamma", "exchange": "NYSE"},
        ]
        snapshots = {
            "AAA": {"latestTrade": {"p": 20}, "dailyBar": {"c": 20, "v": 1000000},
                    "prevDailyBar": {"c": 19}},
            "BBB": {"latestTrade": {"p": 2}, "dailyBar": {"c": 2, "v": 10000000},
                    "prevDailyBar": {"c": 1}},
            "CCC": {"latestTrade": {"p": 10}, "dailyBar": {"c": 10, "v": 1000},
                    "prevDailyBar": {"c": 10}},
        }
        rows = self.discovery.rank_assets(assets, snapshots)
        self.assertEqual([row["symbol"] for row in rows], ["AAA"])
        self.assertEqual(rows[0]["change_pct"], "5.26")
        self.assertEqual(rows[0]["data_feed"], "IEX")

    def test_snapshots_are_chunked_and_get_only(self):
        symbols = [f"S{i:03}" for i in range(205)]
        self.session.get.return_value = FakeResponse({})
        result = self.discovery.snapshots(symbols)
        self.assertEqual(result, {})
        self.assertEqual(self.session.get.call_count, 3)
        self.assertTrue(all(call.kwargs["params"]["feed"] == "iex"
                            for call in self.session.get.call_args_list))

    def test_rejects_unexpected_endpoint(self):
        with self.assertRaises(ValueError):
            self.discovery._get("https://evil.example", "/v2/assets")

    def test_requires_credentials(self):
        with self.assertRaises(ValueError):
            AlpacaMarketDiscovery("", "secret")


if __name__ == "__main__":
    unittest.main()
