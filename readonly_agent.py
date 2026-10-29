"""Read-only portfolio snapshot for the Investopedia simulator.

This module deliberately contains no trading, order-cancellation, or mutation calls.
It is a safe first step toward an AI analyst: collect facts first, analyze them later.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from investopedia_api import InvestopediaApi

ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = ROOT / "credentials.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def load_credentials() -> dict[str, str]:
    if not CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(
            "credentials.json is missing. Create it locally from "
            "credentials_example.json. Never commit or share that file."
        )
    with CREDENTIALS_FILE.open("r", encoding="utf-8") as handle:
        credentials = json.load(handle)
    if not isinstance(credentials, dict):
        raise ValueError("credentials.json must contain a JSON object.")
    if not credentials.get("username") or not credentials.get("password"):
        raise ValueError("credentials.json needs non-empty username and password fields.")
    return credentials


def position_snapshot(position: Any) -> dict[str, Any]:
    fields = (
        "symbol", "description", "underlying_symbol", "quantity",
        "purchase_price", "current_price", "market_value",
        "day_gain_dollar", "day_gain_percent",
        "total_gain_dollar", "total_gain_percent",
    )
    snapshot = {}
    for field in fields:
        if hasattr(position, field):
            try:
                snapshot[field] = json_safe(getattr(position, field))
            except Exception:
                # A missing optional property should not stop the read-only report.
                continue
    return snapshot


def build_snapshot(client: InvestopediaApi) -> dict[str, Any]:
    portfolio = client.portfolio
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "game": portfolio.game_name,
        "portfolio_id": json_safe(portfolio.portfolio_id),
        "account": {
            "account_value": json_safe(portfolio.account_value),
            "cash": json_safe(portfolio.cash),
            "buying_power": json_safe(portfolio.buying_power),
            "annual_return_pct": json_safe(portfolio.annual_return_pct),
        },
        "positions": {
            "long": [position_snapshot(p) for p in portfolio.stock_portfolio],
            "short": [position_snapshot(p) for p in portfolio.short_portfolio],
            "options": [position_snapshot(p) for p in portfolio.option_portfolio],
        },
        "open_orders": [
            {
                "order_id": json_safe(order.order_id),
                "symbol": order.symbol,
                "quantity": json_safe(order.quantity),
                "order_price": json_safe(order.order_price),
                "trade_type": order.trade_type,
                "active": bool(order.active),
            }
            for order in portfolio.open_orders
        ],
        "safety": {
            "read_only": True,
            "orders_submitted": 0,
            "orders_cancelled": 0,
        },
    }


def main() -> int:
    try:
        credentials = load_credentials()
        client = InvestopediaApi(credentials)
        snapshot = build_snapshot(client)
        print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        # Do not print credential data, tokens, HTTP headers, or raw response bodies.
        print(
            f"Read-only snapshot failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
