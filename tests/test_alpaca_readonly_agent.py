"""Offline tests for Alpaca read-only integration; no keys or network are used."""
import unittest
from unittest.mock import Mock

from alpaca_readonly_agent import AlpacaReadOnlyClient, build_snapshot


class AlpacaReadOnlyTests(unittest.TestCase):
    def test_client_uses_fixed_paper_host_and_get_only(self):
        session = Mock()
        response = Mock(ok=True)
        response.json.return_value = []
        session.get.return_value = response
        client = AlpacaReadOnlyClient("test-key", "test-secret", session=session)
        self.assertEqual(client.positions(), [])
        args, kwargs = session.get.call_args
        self.assertEqual(args[0], "https://paper-api.alpaca.markets/v2/positions")
        self.assertEqual(kwargs["headers"]["APCA-API-KEY-ID"], "test-key")
        self.assertEqual(kwargs["headers"]["APCA-API-SECRET-KEY"], "test-secret")
        self.assertEqual(kwargs["timeout"], 15)

    def test_rejects_non_fixed_api_path(self):
        client = AlpacaReadOnlyClient("k", "s", session=Mock())
        with self.assertRaises(ValueError):
            client._get("https://api.alpaca.markets/v2/account")

    def test_http_error_does_not_expose_response_body(self):
        session = Mock()
        response = Mock(ok=False, status_code=401)
        response.text = "SECRET-RESPONSE-BODY"
        session.get.return_value = response
        client = AlpacaReadOnlyClient("k", "s", session=session)
        with self.assertRaisesRegex(RuntimeError, "HTTP 401") as raised:
            client.account()
        self.assertNotIn("SECRET-RESPONSE-BODY", str(raised.exception))

    def test_snapshot_is_marked_read_only(self):
        client = Mock()
        client.account.return_value = {
            "cash": "10000", "portfolio_value": "12000", "equity": "12000"
        }
        client.positions.return_value = [{
            "symbol": "AAPL", "side": "long", "qty": "2",
            "market_value": "400", "private_unexpected_field": "omit-me"
        }]
        client.portfolio_history.return_value = {
            "timestamp": [1, 2], "equity": [11000, 12000],
            "profit_loss": [0, 1000], "profit_loss_pct": [0, 0.1]
        }
        snapshot = build_snapshot(client)
        self.assertEqual(snapshot["mode"], "READ_ONLY")
        self.assertEqual(snapshot["provider"], "Alpaca Paper Trading")
        self.assertEqual(snapshot["safety"]["http_methods_used"], ["GET"])
        self.assertEqual(snapshot["safety"]["orders_submitted"], 0)
        self.assertEqual(snapshot["positions"]["long"][0]["symbol"], "AAPL")
        self.assertNotIn("private_unexpected_field", snapshot["positions"]["long"][0])
        self.assertEqual(snapshot["portfolio_history"]["equity"], [11000, 12000])


if __name__ == "__main__":
    unittest.main()
