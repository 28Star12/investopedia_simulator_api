"""Offline tests for the daily transaction safety guard."""
import tempfile
import unittest
from pathlib import Path

from transaction_guard import (
    MAX_TRANSACTIONS_PER_DAY,
    TransactionGuard,
    TransactionLimitExceeded,
)


class TransactionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Path(self.temp_dir.name) / "guard.sqlite3"
        self.guard = TransactionGuard(self.database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_hard_limit_is_three(self):
        self.assertEqual(MAX_TRANSACTIONS_PER_DAY, 3)

    def test_allows_three_reservations_then_blocks_fourth(self):
        ids = [
            self.guard.reserve("AAPL", "BUY"),
            self.guard.reserve("MSFT", "BUY"),
            self.guard.reserve("NVDA", "SELL"),
        ]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(self.guard.attempts_used_today(), 3)
        with self.assertRaises(TransactionLimitExceeded):
            self.guard.reserve("TSLA", "BUY")
        self.assertEqual(self.guard.attempts_used_today(), 3)

    def test_failed_or_ambiguous_attempt_still_consumes_slot(self):
        attempt_id = self.guard.reserve("AAPL", "BUY")
        self.guard.mark_response_received(attempt_id, "request_error")
        self.assertEqual(self.guard.attempts_used_today(), 1)

    def test_guard_persists_across_instances(self):
        self.guard.reserve("AAPL", "BUY")
        second_guard = TransactionGuard(self.database)
        self.assertEqual(second_guard.attempts_used_today(), 1)


if __name__ == "__main__":
    unittest.main()
