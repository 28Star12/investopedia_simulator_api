"""SQLite persistence for public market events (read-only research data)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


DEFAULT_DB_PATH = Path("data/market_events.sqlite3")
MAX_TEXT_LENGTH = 20_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, limit: int = MAX_TEXT_LENGTH) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    return text[:limit] or None


def _canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if parts.scheme.lower() != "https" or not parts.hostname:
        return None
    # Remove fragments and common tracking parameters without changing the path.
    kept = []
    for item in parts.query.split("&") if parts.query else []:
        key = item.split("=", 1)[0].lower()
        if key.startswith("utm_") or key in {"fbclid", "gclid"}:
            continue
        kept.append(item)
    return urlunsplit(("https", parts.netloc.lower(), parts.path or "/", "&".join(kept), ""))


def _normalise_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


class MarketEventStore:
    """Small SQLite event archive with deterministic deduplication."""

    def __init__(self, db_path: str | Path | None = None):
        configured = db_path or os.environ.get("MARKET_EVENT_DB") or DEFAULT_DB_PATH
        self.db_path = Path(configured)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def _initialise(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("""
                CREATE TABLE IF NOT EXISTS market_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    canonical_url TEXT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    symbols_json TEXT NOT NULL DEFAULT '[]',
                    event_type TEXT NOT NULL DEFAULT 'news',
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(source, content_hash)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_market_events_published ON market_events(published_at DESC)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_market_events_source_id ON market_events(source, source_id)")

    def add_event(self, event: dict[str, Any]) -> dict[str, Any]:
        source = _clean_text(event.get("source"), 100)
        title = _clean_text(event.get("title"), 1000)
        if not source or not title:
            raise ValueError("Each event requires a non-empty source and title.")
        url = _canonical_url(event.get("url"))
        source_id = _clean_text(event.get("source_id"), 500)
        summary = _clean_text(event.get("summary"))
        published_at = _normalise_datetime(event.get("published_at"))
        event_type = _clean_text(event.get("event_type"), 80) or "news"
        symbols = sorted({str(s).strip().upper() for s in (event.get("symbols") or []) if str(s).strip()})
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        identity = source_id or url or (title + "|" + (published_at or ""))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        fetched_at = _utc_now()
        with self._connect() as db:
            cursor = db.execute("""
                INSERT INTO market_events
                (source, source_id, canonical_url, title, summary, published_at,
                 fetched_at, symbols_json, event_type, content_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, content_hash) DO UPDATE SET
                    title=excluded.title,
                    summary=COALESCE(excluded.summary, market_events.summary),
                    canonical_url=COALESCE(excluded.canonical_url, market_events.canonical_url),
                    published_at=COALESCE(excluded.published_at, market_events.published_at),
                    fetched_at=excluded.fetched_at,
                    symbols_json=excluded.symbols_json,
                    metadata_json=excluded.metadata_json
            """, (
                source, source_id, url, title, summary, published_at, fetched_at,
                json.dumps(symbols), event_type, digest,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True)[:MAX_TEXT_LENGTH],
            ))
            row = db.execute(
                "SELECT * FROM market_events WHERE source=? AND content_hash=?",
                (source, digest),
            ).fetchone()
            return self._row_to_dict(row)

    def add_events(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.add_event(event) for event in events]

    def list_events(self, limit: int = 50, symbol: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        query = "SELECT * FROM market_events"
        params: list[Any] = []
        if symbol:
            query += " WHERE symbols_json LIKE ?"
            params.append('%"' + symbol.strip().upper() + '"%')
        query += " ORDER BY COALESCE(published_at, fetched_at) DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as db:
            return [self._row_to_dict(row) for row in db.execute(query, params).fetchall()]

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["symbols"] = json.loads(result.pop("symbols_json"))
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result


    def save_research_cards(self, cards: Iterable[dict[str, Any]]) -> int:
        """Persist the latest explainable research card per symbol."""
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS stock_research (
                    symbol TEXT PRIMARY KEY,
                    generated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            count = 0
            for card in cards:
                symbol = str(card.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                generated_at = _utc_now()
                db.execute("""
                    INSERT INTO stock_research(symbol, generated_at, payload_json)
                    VALUES (?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        generated_at=excluded.generated_at,
                        payload_json=excluded.payload_json
                """, (symbol, generated_at,
                      json.dumps(card, ensure_ascii=False, sort_keys=True)[:MAX_TEXT_LENGTH]))
                count += 1
            return count

    def list_research_cards(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        with self._connect() as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='stock_research'"
            ).fetchone()
            if not exists:
                return []
            rows = db.execute(
                "SELECT symbol, generated_at, payload_json FROM stock_research "
                "ORDER BY generated_at DESC, symbol ASC LIMIT ?", (limit,)
            ).fetchall()
            return [{
                "symbol": row["symbol"],
                "generated_at": row["generated_at"],
                **json.loads(row["payload_json"]),
            } for row in rows]
