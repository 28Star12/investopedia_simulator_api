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

    def test_shortlist_is_limited_to_five_and_requires_core_coverage(self):
        cards = [strong_card("S" + str(i)) for i in range(7)]
        incomplete = strong_card("BAD")
        incomplete["fundamentals"]["metrics"].pop("operating_cash_flow")
        cards.append(incomplete)
        selected = select_shortlist(cards)
        self.assertEqual(len(selected), 5)
        self.assertNotIn("BAD", [item["symbol"] for item in selected])
        self.assertTrue(all(item["investment_review"]["decision"] for item in selected))


if __name__ == "__main__":
    unittest.main()
