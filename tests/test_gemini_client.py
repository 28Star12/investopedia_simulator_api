import unittest
from unittest.mock import Mock

from gemini_client import (
    DEFAULT_MODEL,
    GEMINI_API_URL,
    GeminiAPIError,
    ask_portfolio_question,
)


class GeminiClientTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "provider": "Alpaca Paper Trading",
            "account": {"portfolio_value": "10000", "api_key": "must-not-leak"},
            "positions": {"long": [{"symbol": "ABC", "qty": "2", "secret": "hidden"}]},
            "analysis": {"position_count": 1},
        }

    def test_sends_minimized_context_without_tools_and_returns_text(self):
        session = Mock()
        session.post.return_value.ok = True
        session.post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Your portfolio is concentrated."}]}}]
        }
        answer = ask_portfolio_question(
            "Analyze my exposure", self.snapshot, api_key="test-key", session=session
        )
        self.assertEqual(answer, "Your portfolio is concentrated.")
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], GEMINI_API_URL.format(model=DEFAULT_MODEL))
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "test-key")
        self.assertEqual(kwargs["json"]["generationConfig"]["maxOutputTokens"], 1200)
        self.assertNotIn("tools", kwargs["json"])
        self.assertNotIn("functionCallingConfig", kwargs["json"])
        sent = str(kwargs["json"])
        self.assertNotIn("must-not-leak", sent)
        self.assertNotIn('"secret"', sent)
        self.assertIn('"mode":"READ_ONLY"', sent)
        self.assertIn("Never place, modify, or cancel", sent)

    def test_requires_question_and_key(self):
        with self.assertRaises(ValueError):
            ask_portfolio_question(" ", self.snapshot, api_key="test-key")
        with self.assertRaises(ValueError):
            ask_portfolio_question("Analyze", self.snapshot, api_key="")

    def test_http_error_does_not_expose_response_body_or_key(self):
        session = Mock()
        response = session.post.return_value
        response.ok = False
        response.status_code = 401
        response.json.return_value = {"error": {"message": "Invalid API key"}}
        with self.assertRaises(GeminiAPIError) as caught:
            ask_portfolio_question("Analyze", self.snapshot, api_key="test-key", session=session)
        self.assertIn("HTTP 401", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_429_has_safe_quota_diagnostic(self):
        session = Mock()
        response = session.post.return_value
        response.ok = False
        response.status_code = 429
        response.json.return_value = {
            "error": {"status": "RESOURCE_EXHAUSTED", "message": "Quota exceeded"}
        }
        with self.assertRaises(GeminiAPIError) as caught:
            ask_portfolio_question("Analyze", self.snapshot, api_key="test-key", session=session)
        self.assertIn("HTTP 429", str(caught.exception))
        self.assertIn("RESOURCE_EXHAUSTED", str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_rejects_unexpected_response_shape(self):
        session = Mock()
        session.post.return_value.ok = True
        session.post.return_value.json.return_value = {"unexpected": True}
        with self.assertRaises(GeminiAPIError):
            ask_portfolio_question("Analyze", self.snapshot, api_key="test-key", session=session)


if __name__ == "__main__":
    unittest.main()
