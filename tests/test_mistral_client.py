import json
import unittest
from unittest.mock import Mock

from mistral_client import (
    DEFAULT_MODEL,
    MISTRAL_CHAT_URL,
    MistralAPIError,
    ask_portfolio_question,
)


class MistralClientTests(unittest.TestCase):
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
            "choices": [{"message": {"content": "Your portfolio is concentrated."}}]
        }

        answer = ask_portfolio_question(
            "Analyze my exposure",
            self.snapshot,
            api_key="test-key",
            session=session,
        )

        self.assertEqual(answer, "Your portfolio is concentrated.")
        args, kwargs = session.post.call_args
        self.assertEqual(args[0], MISTRAL_CHAT_URL)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(kwargs["json"]["model"], DEFAULT_MODEL)
        self.assertEqual(kwargs["json"]["tool_choice"], "none")
        self.assertNotIn("tools", kwargs["json"])
        user_content = kwargs["json"]["messages"][1]["content"]
        self.assertNotIn("must-not-leak", user_content)
        self.assertNotIn('"secret"', user_content)
        self.assertIn('"mode":"READ_ONLY"', user_content)

    def test_requires_non_empty_question_and_key(self):
        with self.assertRaises(ValueError):
            ask_portfolio_question(" ", self.snapshot, api_key="test-key")
        with self.assertRaises(ValueError):
            ask_portfolio_question("Analyze", self.snapshot, api_key="")

    def test_reports_http_status_without_response_body(self):
        session = Mock()
        session.post.return_value.ok = False
        session.post.return_value.status_code = 401
        session.post.return_value.text = "secret response body"

        with self.assertRaisesRegex(MistralAPIError, "HTTP 401") as caught:
            ask_portfolio_question(
                "Analyze",
                self.snapshot,
                api_key="test-key",
                session=session,
            )
        self.assertNotIn("secret response body", str(caught.exception))

    def test_rejects_unexpected_response_shape(self):
        session = Mock()
        session.post.return_value.ok = True
        session.post.return_value.json.return_value = {"unexpected": True}
        with self.assertRaises(MistralAPIError):
            ask_portfolio_question(
                "Analyze",
                self.snapshot,
                api_key="test-key",
                session=session,
            )


if __name__ == "__main__":
    unittest.main()
