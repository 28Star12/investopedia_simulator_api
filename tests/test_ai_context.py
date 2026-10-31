import unittest

from ai_context import AI_SYSTEM_INSTRUCTIONS, build_ai_context


class AIContextTests(unittest.TestCase):
    def test_builds_minimized_read_only_context(self):
        snapshot = {
            "provider": "Alpaca Paper Trading",
            "generated_at": "2026-10-29T12:00:00+00:00",
            "mode": "READ_ONLY",
            "account": {
                "id": "must-not-leak",
                "status": "ACTIVE",
                "currency": "USD",
                "cash": "5000",
                "portfolio_value": "12000",
                "api_key": "must-not-leak",
            },
            "positions": {
                "long": [{
                    "symbol": "ABC",
                    "qty": "10",
                    "market_value": "1000",
                    "secret_field": "must-not-leak",
                }],
                "short": [],
                "options": [],
                "other": [],
            },
            "analysis": {"position_count": 1, "flags": []},
            "safety": {"orders_submitted": 99},
        }

        context = build_ai_context(snapshot)

        self.assertEqual(context["mode"], "READ_ONLY")
        self.assertEqual(context["account"]["portfolio_value"], "12000")
        self.assertNotIn("id", context["account"])
        self.assertNotIn("api_key", context["account"])
        self.assertNotIn("secret_field", context["positions"][0])
        self.assertEqual(context["safety"]["orders_submitted"], 0)
        self.assertEqual(context["analysis"], snapshot["analysis"])

    def test_handles_missing_optional_sections(self):
        context = build_ai_context({})
        self.assertEqual(context["account"], {})
        self.assertEqual(context["positions"], [])
        self.assertEqual(context["mode"], "READ_ONLY")

    def test_rejects_non_dictionary_snapshot(self):
        with self.assertRaises(TypeError):
            build_ai_context([])

    def test_instructions_forbid_trading_and_fabrication(self):
        self.assertIn("Never place, modify, or cancel", AI_SYSTEM_INSTRUCTIONS)
        self.assertIn("Do not invent", AI_SYSTEM_INSTRUCTIONS)
        self.assertIn("not financial advice", AI_SYSTEM_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
