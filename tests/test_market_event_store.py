import tempfile
import unittest
from pathlib import Path

from market_event_store import MarketEventStore, _canonical_url, _normalise_datetime
from market_news_collector import parse_feed, validate_feed_url


class MarketEventStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MarketEventStore(Path(self.temp.name) / "events.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_insert_and_deduplicate_by_source_id(self):
        event = {"source": "test", "source_id": "abc", "title": "Market update", "url": "https://example.com/a?utm_source=x"}
        first = self.store.add_event(event)
        second = self.store.add_event({**event, "title": "Updated headline"})
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list_events()), 1)
        self.assertEqual(second["title"], "Updated headline")

    def test_different_sources_are_not_collapsed(self):
        self.store.add_event({"source": "a", "source_id": "1", "title": "Same"})
        self.store.add_event({"source": "b", "source_id": "1", "title": "Same"})
        self.assertEqual(len(self.store.list_events()), 2)

    def test_rejects_missing_required_fields(self):
        with self.assertRaises(ValueError):
            self.store.add_event({"source": "test", "title": " "})

    def test_normalises_timestamps_and_symbols(self):
        item = self.store.add_event({"source": "test", "title": "Headline", "published_at": "2026-10-29T12:00:00-05:00", "symbols": ["aapl", "AAPL", " msft "]})
        self.assertTrue(item["published_at"].endswith("+00:00"))
        self.assertEqual(item["symbols"], ["AAPL", "MSFT"])

    def test_symbol_filter_is_parameterized(self):
        self.store.add_event({"source": "test", "title": "AAPL item", "symbols": ["AAPL"]})
        self.store.add_event({"source": "test", "title": "MSFT item", "symbols": ["MSFT"]})
        self.assertEqual(len(self.store.list_events(symbol='AAPL" OR 1=1 --')), 0)
        self.assertEqual(len(self.store.list_events(symbol="AAPL")), 1)

    def test_canonical_url_drops_tracking_parameters(self):
        self.assertEqual(_canonical_url("https://EXAMPLE.com/story?utm_source=x&id=2#top"), "https://example.com/story?id=2")
        self.assertIsNone(_canonical_url("http://example.com/story"))

    def test_invalid_datetime_is_ignored(self):
        self.assertIsNone(_normalise_datetime("not-a-date"))


class RSSParserTests(unittest.TestCase):
    def test_parses_rss_items(self):
        xml = """<rss><channel><item><title>Apple update</title><link>https://www.cnbc.com/story</link><guid>story-1</guid><pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate><description>Company news</description></item></channel></rss>"""
        events = parse_feed(xml, "cnbc")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source_id"], "story-1")
        self.assertEqual(events[0]["summary"], "Company news")
        self.assertTrue(events[0]["published_at"].endswith("+00:00"))

    def test_parses_atom_link(self):
        xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Market</title><id>tag:example,1</id><link href="https://www.cnbc.com/a"/></entry></feed>"""
        self.assertEqual(parse_feed(xml, "atom")[0]["url"], "https://www.cnbc.com/a")

    def test_rejects_dtd_and_large_payload(self):
        with self.assertRaises(ValueError):
            parse_feed('<!DOCTYPE x [<!ENTITY e "x">]><rss/>', "bad")
        with self.assertRaises(ValueError):
            parse_feed("x" * 2_000_001, "large")

    def test_feed_host_allowlist(self):
        self.assertEqual(validate_feed_url("https://www.cnbc.com/rss"), "https://www.cnbc.com/rss")
        for url in ("http://www.cnbc.com/rss", "https://cnbc.com.attacker.test/rss", "https://example.com/rss"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_feed_url(url)


if __name__ == "__main__":
    unittest.main()
