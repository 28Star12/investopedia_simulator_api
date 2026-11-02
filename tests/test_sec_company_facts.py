import unittest
from unittest.mock import Mock
from sec_company_facts import SECCompanyFacts, TICKERS_URL, FACTS_URL

class Response:
    content = b'{}'
    def __init__(self, payload): self.payload = payload
    def raise_for_status(self): pass
    def json(self): return self.payload

class SECFactsTests(unittest.TestCase):
    def test_ticker_map_and_annual_metrics(self):
        session=Mock()
        session.headers={}
        ticker_payload={"0":{"ticker":"AAA","cik_str":123}}
        facts={"facts":{"us-gaap":{
            "Revenues":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","filed":"2026-02-01","val":1000}]}},
            "OperatingIncomeLoss":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","val":100}]}},
            "NetIncomeLoss":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","val":80}]}},
            "Assets":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","val":900}]}},
            "Liabilities":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","val":300}]}},
            "NetCashProvidedByUsedInOperatingActivities":{"units":{"USD":[{"form":"10-K","end":"2025-12-31","val":120}]}}
        }}}
        session.get.side_effect=[Response(ticker_payload),Response(facts)]
        client=SECCompanyFacts("Market Monitor contact: test@example.com",session)
        result=client.collect(["AAA"])["AAA"]
        self.assertEqual(result["status"],"AVAILABLE")
        self.assertEqual(result["metrics"]["revenue"]["value"],1000)
        self.assertAlmostEqual(result["ratios"]["liabilities_to_assets"],1/3)

    def test_rejects_bad_user_agent(self):
        with self.assertRaises(ValueError): SECCompanyFacts("bad")

if __name__ == "__main__": unittest.main()
