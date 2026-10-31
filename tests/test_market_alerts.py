import unittest
from market_alerts import generate_alerts

class MarketAlertTests(unittest.TestCase):
    def test_price_alert_thresholds_and_daily_deduplication(self):
        candidates = [{"symbol":"AAA","change_pct":5.2},{"symbol":"BBB","change_pct":-3.5},{"symbol":"CCC","change_pct":1.2}]
        alerts = generate_alerts(candidates, [], now="2026-10-30T12:00:00+00:00")
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0]["severity"], "HIGH")
        self.assertEqual(alerts[1]["severity"], "MEDIUM")
        again = generate_alerts(candidates, [], now="2026-10-30T18:00:00+00:00")
        self.assertEqual([x["alert_key"] for x in alerts], [x["alert_key"] for x in again])

    def test_news_and_sec_filing_alerts(self):
        events = [
            {"id":1,"source":"alpaca_news","source_id":"news-1","event_type":"news","title":"Company faces fraud investigation","symbols":["AAA"],"canonical_url":"https://example.com/news"},
            {"id":2,"source":"sec_edgar","source_id":"filing-1","event_type":"sec_filing","title":"AAA Form 8-K","symbols":["AAA"],"metadata":{"form":"8-K"},"canonical_url":"https://www.sec.gov/filing"},
        ]
        alerts = generate_alerts([], events, now="2026-10-30T12:00:00+00:00")
        self.assertEqual(len(alerts), 2)
        self.assertEqual({x["alert_type"] for x in alerts}, {"negative_news","sec_filing"})
        self.assertEqual(next(x for x in alerts if x["alert_type"]=="sec_filing")["severity"], "HIGH")

if __name__ == "__main__":
    unittest.main()
