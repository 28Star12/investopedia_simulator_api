import tempfile
import unittest
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
from market_event_store import MarketEventStore
from market_research import AlpacaNewsCollector, build_research_cards, _news_sentiment

class FakeResponse:
    ok = True
    status_code = 200
    def __init__(self, payload): self.payload = payload
    def json(self): return self.payload

class MarketResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = MarketEventStore(self.temp.name + '/events.sqlite3')
    def tearDown(self): self.temp.cleanup()
    def test_news_collection(self):
        session = Mock()
        session.get.return_value = FakeResponse({'news': [{'id': 123, 'headline': 'Company beats estimates and raises guidance', 'summary': 'Record revenue reported.', 'url': 'https://example.com/story', 'created_at': '2026-10-28T12:00:00Z', 'symbols': ['AAA'], 'author': 'Reporter', 'images': []}]})
        result = AlpacaNewsCollector('key', 'secret', session).collect(['AAA'], self.store)
        self.assertEqual(result['stored_total'], 1)
        self.assertEqual(session.get.call_args.args[0], 'https://data.alpaca.markets/v1beta1/news')
        self.assertEqual(self.store.list_events(symbol='AAA')[0]['source'], 'alpaca_news')
    def test_research_card_is_explicit_about_missing_fundamentals(self):
        self.store.add_event({'source':'alpaca_news','source_id':'n1','url':'https://example.com/story','title':'Company beats estimates','summary':'Raises guidance after record revenue.','symbols':['AAA'],'event_type':'news'})
        self.store.add_event({'source':'sec_edgar','source_id':'0000000001-26-000001','url':'https://www.sec.gov/Archives/example.htm','title':'AAA SEC Form 10-Q','symbols':['AAA'],'event_type':'sec_filing','metadata':{'form':'10-Q'}})
        cards = build_research_cards([{'symbol':'AAA','name':'Alpha','price':'25','change_pct':'2.5','dollar_volume':'50000000','discovery_score':4.2,'data_feed':'IEX'}], self.store)
        self.assertEqual(cards[0]['research_status'], 'POSITIVE_NEWS_WATCH')
        self.assertEqual(cards[0]['sec_filings'][0]['form'], '10-Q')
        self.assertEqual(cards[0]['fundamentals']['status'], 'NOT_CONFIGURED')
        self.assertEqual(cards[0]['sentiment']['status'], 'AVAILABLE')
        self.assertGreater(cards[0]['sentiment']['score'], 0.5)
        self.assertEqual(cards[0]['sentiment']['mood'], 'CROWDED_OPTIMISM')
    def test_negative_news_marks_risk(self):
        self.store.add_event({'source':'alpaca_news','source_id':'n2','url':'https://example.com/risk','title':'Company faces fraud investigation','summary':'Going concern warning.','symbols':['BBB'],'event_type':'news'})
        cards = build_research_cards([{'symbol':'BBB','name':'Beta'}], self.store)
        self.assertEqual(cards[0]['research_status'], 'RISK_REVIEW')
        self.assertEqual(cards[0]['sentiment']['mood'], 'PANIC_OR_HIGH_RISK')
        self.assertLess(cards[0]['sentiment']['score'], 0.5)

    def test_sentiment_excludes_old_news_and_weights_recent_news_more(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        events = [
            {"title": "Company beats estimates and raises guidance",
             "published_at": (now - timedelta(days=1)).isoformat()},
            {"title": "Company faces fraud investigation and bankruptcy",
             "published_at": (now - timedelta(days=30)).isoformat()},
        ]
        result = _news_sentiment(events, now=now)
        self.assertEqual(result["status"], "AVAILABLE")
        self.assertGreater(result["score"], 0.5)
        self.assertEqual(result["articles_analyzed"], 1)
        self.assertEqual(result["stale_articles_excluded"], 1)
        self.assertEqual(result["method"], "recency_weighted_news_keyword_tone_v2")

    def test_sentiment_is_unavailable_when_all_news_is_stale_or_undated(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)
        result = _news_sentiment([
            {"title": "Company beats estimates", "published_at": "2026-09-01T12:00:00Z"},
            {"title": "Company raises guidance"},
        ], now=now)
        self.assertEqual(result["status"], "NO_RECENT_NEWS")
        self.assertIsNone(result["score"])
        self.assertEqual(result["stale_articles_excluded"], 1)
        self.assertEqual(result["undated_articles_excluded"], 1)

    def test_no_news_has_no_fabricated_neutral_score(self):
        cards = build_research_cards([{'symbol':'CCC','name':'Gamma'}], self.store)
        self.assertEqual(cards[0]['sentiment']['status'], 'NO_NEWS')
        self.assertIsNone(cards[0]['sentiment']['score'])

if __name__ == '__main__': unittest.main()
