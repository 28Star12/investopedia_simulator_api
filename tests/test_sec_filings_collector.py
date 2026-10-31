import tempfile
import unittest
from unittest.mock import Mock

from sec_filings_collector import SECFilingsCollector, TICKERS_URL, SUBMISSIONS_URL
from market_event_store import MarketEventStore


class FakeResponse:
    def __init__(self, payload):
        import json
        self.content = json.dumps(payload).encode()
        self._payload = payload
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload


class SECFilingsCollectorTests(unittest.TestCase):
    def setUp(self):
        self.session = Mock()
        self.collector = SECFilingsCollector("MarketMonitor contact@example.com", self.session)
        self.temp = tempfile.TemporaryDirectory()
        self.store = MarketEventStore(self.temp.name + "/events.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_requires_identifying_user_agent(self):
        with self.assertRaises(ValueError):
            SECFilingsCollector("short")

    def test_collects_recent_supported_filings_and_deduplicates(self):
        tickers = {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
        recent = {"filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001", "0000320193-26-000002"],
            "filingDate": ["2026-10-28", "2026-10-27"],
            "form": ["8-K", "4"],
            "primaryDocument": ["a.htm", "b.htm"],
            "primaryDocDescription": ["Current report", "Statement of changes"],
        }}}
        self.session.get.side_effect = [FakeResponse(tickers), FakeResponse(recent), FakeResponse(recent)]
        first = self.collector.collect(["aapl"], self.store)
        second = self.collector.collect(["AAPL"], self.store)
        self.assertEqual(first["stored_total"], 1)
        self.assertEqual(second["stored_total"], 1)
        events = self.store.list_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "sec_filing")
        self.assertEqual(events[0]["symbols"], ["AAPL"])
        self.assertIn("/Archives/edgar/data/320193/000032019326000001/a.htm", events[0]["canonical_url"])

    def test_unknown_ticker_is_reported_without_submissions_request(self):
        self.session.get.return_value = FakeResponse({})
        result = self.collector.collect(["NOTREAL"], self.store)
        self.assertIn("not found", result["sources"][0]["error"])
        self.assertEqual(self.session.get.call_count, 1)

    def test_invalid_document_path_is_ignored(self):
        recent = {"filings": {"recent": {
            "accessionNumber": ["0000320193-26-000001"],
            "filingDate": ["2026-10-28"], "form": ["10-Q"],
            "primaryDocument": ["../bad.htm"], "primaryDocDescription": [""],
        }}}
        self.session.get.return_value = FakeResponse(recent)
        result = self.collector.collect_symbol("AAPL", "0000320193", self.store)
        self.assertEqual(result["fetched"], 0)

    def test_ticker_validation(self):
        result = self.collector.collect(["AAPL;DROP"], self.store)
        self.assertIn("Invalid ticker", result["sources"][0]["error"])


if __name__ == "__main__":
    unittest.main()
