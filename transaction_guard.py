"""Hard limit for transaction submissions.

The limit is intentionally hard-coded to three attempts per US market calendar day.
Every reserved submission consumes a slot, including ambiguous failures, so crashes
or network timeouts cannot silently grant extra attempts. This module uses SQLite
transactions to serialize concurrent callers.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

MAX_TRANSACTIONS_PER_DAY = 3
MARKET_TIMEZONE = ZoneInfo("America/New_York")
DEFAULT_DATABASE = Path(__file__).resolve().parent / ".transaction_guard.sqlite3"


class TransactionLimitExceeded(RuntimeError):
    """Raised when the daily transaction submission limit has been reached."""


class TransactionGuard:
    def __init__(self, database_path: str | Path = DEFAULT_DATABASE) -> None:
        self.database_path = str(database_path)
        self._initialize()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(MARKET_TIMEZONE)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS transaction_attempts (
                    attempt_id TEXT PRIMARY KEY,
                    trading_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_attempts_date
                ON transaction_attempts(trading_date)
            """)

    def reserve(self, symbol: str, transaction_type: str) -> str:
        """Atomically reserve one daily slot before sending a transaction request."""
        clean_symbol = str(symbol).strip().upper()
        clean_type = str(transaction_type).strip().upper()
        if not clean_symbol or not clean_type:
            raise ValueError("A symbol and transaction type are required.")

        now = self._now()
        trading_date = now.date().isoformat()
        attempt_id = str(uuid.uuid4())
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM transaction_attempts WHERE trading_date = ?",
                (trading_date,),
            ).fetchone()
            used = int(row["total"])
            if used >= MAX_TRANSACTIONS_PER_DAY:
                connection.rollback()
                raise TransactionLimitExceeded(
                    f"Daily transaction limit reached ({MAX_TRANSACTIONS_PER_DAY} per day, "
                    f"America/New_York). No transaction was sent."
                )
            connection.execute(
                """INSERT INTO transaction_attempts
                   (attempt_id, trading_date, symbol, transaction_type, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    attempt_id, trading_date, clean_symbol, clean_type,
                    "reserved", now.isoformat(),
                ),
            )
            connection.commit()
            return attempt_id
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise
        finally:
            connection.close()

    def mark_submitted(self, attempt_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE transaction_attempts SET status = 'submitted' WHERE attempt_id = ?",
                (attempt_id,),
            )

    def mark_response_received(self, attempt_id: str, status: str = "response_received") -> None:
        # This updates audit status only; the reserved slot is never refunded.
        with self._connect() as connection:
            connection.execute(
                "UPDATE transaction_attempts SET status = ? WHERE attempt_id = ?",
                (str(status)[:40], attempt_id),
            )

    def attempts_used_today(self) -> int:
        trading_date = self._now().date().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS total FROM transaction_attempts WHERE trading_date = ?",
                (trading_date,),
            ).fetchone()
            return int(row["total"])


_default_guard: TransactionGuard | None = None


def get_transaction_guard() -> TransactionGuard:
    global _default_guard
    if _default_guard is None:
        _default_guard = TransactionGuard()
    return _default_guard
