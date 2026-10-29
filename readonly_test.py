"""Safe, read-only smoke test for the Investopedia Simulator API.

This script only reads portfolio data. It never submits, cancels, or modifies trades.
Run from the repository root after authentication has been configured.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from investopedia_api import InvestopediaApi


ROOT = Path(__file__).resolve().parent
CREDENTIALS_FILE = ROOT / "credentials.json"


def load_credentials() -> dict[str, str]:
    if not CREDENTIALS_FILE.is_file():
        raise FileNotFoundError(
            "credentials.json was not found. Create it locally from "
            "credentials_example.json; do not commit it or share its contents."
        )

    with CREDENTIALS_FILE.open("r", encoding="utf-8") as handle:
        credentials = json.load(handle)

    if not isinstance(credentials, dict):
        raise ValueError("credentials.json must contain a JSON object.")
    if not credentials.get("username") or not credentials.get("password"):
        raise ValueError(
            "credentials.json must contain non-empty username and password fields."
        )
    return credentials


def main() -> int:
    try:
        credentials = load_credentials()
        # InvestopediaApi initialization reads portfolio data; this test does not
        # call any buy, sell, short, cover, option, or order-cancellation methods.
        client = InvestopediaApi(credentials)
        portfolio = client.portfolio

        print("\nREAD-ONLY CONNECTION TEST PASSED")
        print(f"Game: {portfolio.game_name}")
        print(f"Portfolio ID: {portfolio.portfolio_id}")
        print(f"Account value: {portfolio.account_value}")
        print(f"Cash: {portfolio.cash}")
        print(f"Buying power: {portfolio.buying_power}")
        print(f"Long positions: {len(portfolio.stock_portfolio)}")
        print(f"Short positions: {len(portfolio.short_portfolio)}")
        print(f"Option positions: {len(portfolio.option_portfolio)}")
        print(f"Open orders: {len(portfolio.open_orders)}")
        print("\nNo trades were submitted or cancelled.")
        return 0
    except Exception as exc:
        # Avoid printing credentials, request headers, or token data.
        print(f"READ-ONLY CONNECTION TEST FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
