import unittest
from datetime import date
from earnings_calendar import detect_earnings_announcements, extract_explicit_date
from market_event_store import MarketEventStore
import tempfile


class EarningsCalendarTests(unittest.TestCase):
    def test_extracts_full_dates_only(self):
        self.assertEqual(extract_explicit_date("reports Q3 earnings on November 5, 2026"), date(2026, 11, 5))
        self.assertEqual(extract_explicit_date("results scheduled for 2026-11-05"), date(2026, 11, 5))
        self.assertEqual(extract_explicit_date("results on 5 November 2026"), date(2026, 11, 5))
        self.assertIsNone(extract_explicit_date("earnings on November 5"))
        self.assertIsNone(extract_explicit_date("earnings on February 30, 2026"))

    def test_requires_earnings_announcement_and_keeps_unknown_date(self):
        event = {"source":"alpaca_news","source_id":"abc","canonical_url":"https://example.com/a",
                 "title":"ABC will report earnings soon","symbols":["abc"],"event_type":"news"}
        records = detect_earnings_announcements([event], now=date(2026, 10, 31))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["metadata"]["status"], "DATE_UNCONFIRMED")
        self.assertIsNone(records[0]["metadata"]["earnings_date"])
        self.assertEqual(records[0]["symbols"], ["ABC"])
        self.assertEqual(detect_earnings_announcements([{**event, "title":"ABC reported strong earnings"}]), [])

    def test_dated_announcement_preserves_original_source(self):
        event = {"source":"alpaca_news","source_id":"123","canonical_url":"https://example.com/a",
                 "title":"ABC will report quarterly results on November 5, 2026",
                 "published_at":"2026-10-28T12:00:00Z","symbols":["abc"],"event_type":"news"}
        record = detect_earnings_announcements([event], now=date(2026, 10, 31))[0]
        self.assertEqual(record["metadata"]["earnings_date"], "2026-11-05")
        self.assertEqual(record["metadata"]["status"], "DATE_CONFIRMED")
        self.assertEqual(record["url"], event["canonical_url"])
        self.assertEqual(record["metadata"]["original_source"], "alpaca_news")

    def test_collect_persists_calendar_records(self):
        with tempfile.TemporaryDirectory() as directory:
            store = MarketEventStore(directory + "/events.sqlite3")
            store.add_event({"source":"news","source_id":"x","url":"https://example.com/x",
                "title":"XYZ will report earnings on November 5, 2026","symbols":["XYZ"],"event_type":"news"})
            from earnings_calendar import collect_earnings_calendar
            result = collect_earnings_calendar(store, now=date(2026, 10, 31))
            self.assertEqual(result["confirmed_dates"], 1)
            saved = [x for x in store.list_events(limit=50) if x["event_type"] == "earnings_calendar"]
            self.assertEqual(len(saved), 1)


if __name__ == "__main__":
    unittest.main()
