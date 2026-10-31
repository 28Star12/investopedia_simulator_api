import unittest
from decision_engine import classify_research

class DecisionEngineTests(unittest.TestCase):
    def test_missing_fundamentals_stays_watch(self):
        result = classify_research({"fundamentals":{"status":"NO_XBRL_FACTS","metrics":{},"ratios":{}}, "news_score_heuristic":8})
        self.assertEqual(result["decision"], "WATCH")
        self.assertTrue(result["missing_data"])

    def test_strong_fundamentals_can_be_candidate(self):
        metrics = {k:{"value":v} for k,v in {
            "revenue":1000,"operating_income":150,"net_income":120,
            "operating_cash_flow":180,"assets":1000,"liabilities":400}.items()}
        result = classify_research({"fundamentals":{"metrics":metrics,"ratios":{"liabilities_to_assets":0.4}}, "news_score_heuristic":4, "risk_terms":[]})
        self.assertEqual(result["decision"], "CANDIDATE")

    def test_losses_and_negative_cashflow_can_be_avoid(self):
        metrics = {k:{"value":v} for k,v in {
            "revenue":1000,"operating_income":-150,"net_income":-120,
            "operating_cash_flow":-180,"assets":1000,"liabilities":900}.items()}
        result = classify_research({"fundamentals":{"metrics":metrics,"ratios":{"liabilities_to_assets":0.9}}, "news_score_heuristic":-5, "risk_terms":["fraud"]})
        self.assertEqual(result["decision"], "AVOID")

if __name__ == "__main__":
    unittest.main()
