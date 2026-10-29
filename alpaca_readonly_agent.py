"""Read-only Alpaca Paper Trading snapshot.

This module only issues HTTP GET requests to Alpaca's fixed paper-trading host.
It has no order submission, cancellation, or account-mutation implementation.
Set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the local environment.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import requests

from portfolio_analysis import analyze_snapshot

BASE_URL = "https://paper-api.alpaca.markets"
TIMEOUT_SECONDS = 15


class AlpacaReadOnlyClient:
    """Minimal read-only client pinned to Alpaca's paper-trading API."""

    def __init__(self, key_id: str, secret_key: str, session: Any = None):
        if not key_id or not secret_key:
            raise ValueError("Both Alpaca Paper Trading API key values are required.")
        self.key_id = key_id
        self.secret_key = secret_key
        self.session = session or requests.Session()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        # Internal callers pass fixed paths only; never accept a user-provided URL.
        if not path.startswith("/v2/") or "://" in path or ".." in path:
            raise ValueError("Invalid fixed API path.")
        response = self.session.get(
            BASE_URL + path,
            headers={
                "APCA-API-KEY-ID": self.key_id,
                "APCA-API-SECRET-KEY": self.secret_key,
                "Accept": "application/json",
            },
            params=params,
            timeout=TIMEOUT_SECONDS,
        )
        if not response.ok:
            # Deliberately do not print response bodies, headers, or credentials.
            raise RuntimeError(f"Alpaca Paper API returned HTTP {response.status_code}.")
        return response.json()

    def account(self) -> dict[str, Any]:
        return self._get("/v2/account")

    def positions(self) -> list[dict[str, Any]]:
        result = self._get("/v2/positions")
        if not isinstance(result, list):
            raise RuntimeError("Unexpected positions response format.")
        return result

    def portfolio_history(self) -> dict[str, Any]:
        return self._get(
            "/v2/account/portfolio/history",
            params={"period": "1M", "timeframe": "1D"},
        )


def _safe(value: Any) -> Any:
    """Make values JSON-safe without converting arrays or numbers to strings."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def build_snapshot(client: AlpacaReadOnlyClient) -> dict[str, Any]:
    account = client.account()
    raw_positions = client.positions()
    history = client.portfolio_history()

    positions = []
    for item in raw_positions:
        # Whitelist fields; never dump arbitrary API response properties.
        positions.append({
            field: _safe(item[field])
            for field in (
                "symbol", "asset_class", "qty", "side", "avg_entry_price",
                "current_price", "market_value", "cost_basis", "unrealized_pl",
                "unrealized_plpc", "unrealized_intraday_pl",
                "unrealized_intraday_plpc", "change_today",
            )
            if field in item
        })

    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": "Alpaca Paper Trading",
        "mode": "READ_ONLY",
        "account": {
            field: _safe(account[field])
            for field in (
                "id", "status", "currency", "cash", "portfolio_value",
                "buying_power", "equity", "last_equity", "long_market_value",
                "short_market_value", "initial_margin", "maintenance_margin",
                "daytrade_count", "pattern_day_trader", "trading_blocked",
                "transfers_blocked", "account_blocked",
            )
            if field in account
        },
        "positions": {
            "long": [p for p in positions if p.get("side") == "long"],
            "short": [p for p in positions if p.get("side") == "short"],
            "other": [p for p in positions if p.get("side") not in ("long", "short")],
            "options": [],
        },
        "portfolio_history": {
            field: _safe(history[field])
            for field in ("timestamp", "equity", "profit_loss", "profit_loss_pct", "base_value", "timeframe")
            if field in history
        },
        "safety": {
            "read_only": True,
            "environment": "paper",
            "orders_submitted": 0,
            "orders_cancelled": 0,
            "http_methods_used": ["GET"],
        },
    }
    # Reuse the existing diagnostics schema, which calls total account value account_value.\n    snapshot["account"]["account_value"] = snapshot["account"].get("portfolio_value")\n    snapshot["analysis"] = analyze_snapshot(snapshot)
    return snapshot


def main() -> int:
    key_id = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")
    if not key_id or not secret_key:
        print(
            "Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY environment variable. "
            "Use Paper Trading keys and keep them private.",
            file=sys.stderr,
        )
        return 2
    try:
        snapshot = build_snapshot(AlpacaReadOnlyClient(key_id, secret_key))
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return 0
    except requests.RequestException as exc:
        # Avoid printing exception details that may contain request metadata.
        print(f"Alpaca read-only snapshot failed: network error ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Alpaca read-only snapshot failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
