import unittest
from datetime import date
from investment_committee import review_stock, select_shortlist


def strong_card(symbol="AAA"):
    metrics = {
        "revenue": {"value": 1000, "filed": date.today().isoformat()},
        "operating_income": {"value": 180, "filed": date.today().isoformat()},
        "net_income": {"value": 120, "filed": date.today().isoformat()},
        "operating_cash_flow": {"value": 160, "filed": date.today().isoformat()},
    }
    return {
        "symbol": symbol,
        "company": symbol + " Inc.",
        "fundamentals": {
            "status": "AVAILABLE",
            "metrics": metrics,
            "ratios": {
                "operating_margin": 0.18,
                "net_margin": 0.12,
                "liabilities_to_assets": 0.4,
            },
        },
        "news_score_heuristic": 4,
        "technical": {"status": "AVAILABLE", "score": 0.85},
        "sentiment": {"status": "AVAILABLE", "score": 0.80},
        "risk_terms": [],
        "market": {"daily_dollar_volume": "25000000", "price": "50"},
        "discovery_score": 20,
    }


class InvestmentCommitteeTests(unittest.TestCase):
    def test_strong_recent_company_can_pass_paper_buy_screen(self):
        result = review_stock(strong_card())
        self.assertEqual(result["decision"], "PAPER_BUY_CANDIDATE")
        self.assertGreaterEqual(result["score"], 75)
        self.assertEqual(result["missing_data"], [])

    def test_risk_or_stale_data_blocks_paper_buy_screen(self):
        card = strong_card()
        card["risk_terms"] = ["fraud"]
        self.assertEqual(review_stock(card)["decision"], "DO_NOT_BUY")
        stale = strong_card()
        stale["fundamentals"]["metrics"]["revenue"]["filed"] = "2023-01-01"
        stale["fundamentals"]["metrics"]["operating_income"]["filed"] = "2023-01-01"
        stale["fundamentals"]["metrics"]["net_income"]["filed"] = "2023-01-01"
        stale["fundamentals"]["metrics"]["operating_cash_flow"]["filed"] = "2023-01-01"
        self.assertEqual(review_stock(stale)["decision"], "DO_NOT_BUY")

    def test_shortlist_is_limited_to_five_and_ranks_complete_research_first(self):
        cards = [strong_card("S" + str(i)) for i in range(7)]
        incomplete = strong_card("BAD")
        incomplete["fundamentals"]["metrics"].pop("operating_cash_flow")
        cards.append(incomplete)
        selected = select_shortlist(cards)
        self.assertEqual(len(selected), 5)
        self.assertNotIn("BAD", [item["symbol"] for item in selected])
        self.assertTrue(all(item["investment_review"]["decision"] for item in selected))

    def test_shortlist_keeps_stock_when_sec_fundamentals_are_missing(self):
        card = {"symbol": "XYZ", "fundamentals": {"status": "NOT_CONFIGURED", "metrics": {}, "ratios": {}},
                "market": {"daily_dollar_volume": "5000000"}, "discovery_score": 12}
        selected = select_shortlist([card])
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["investment_review"]["decision"], "RESEARCH_INCOMPLETE")
        self.assertIn("revenue", selected[0]["investment_review"]["missing_data"])

    def test_combined_score_uses_equal_weights(self):
        result = review_stock(strong_card())
        self.assertAlmostEqual(result["combined_score"], (0.85 + 0.80 + result["fundamental_score"]) / 3, places=3)
        self.assertEqual(result["weights"], {"technical": 1/3, "sentiment": 1/3, "fundamental": 1/3})


if __name__ == "__main__":
    unittest.main()
