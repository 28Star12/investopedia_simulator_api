"""Ask Mistral a question about the current Alpaca Paper portfolio snapshot.

This script only reads the account snapshot and sends minimized data to Mistral.
It has no trading or order-management operations.
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

from alpaca_readonly_agent import AlpacaReadOnlyClient, build_snapshot
from mistral_client import MistralAPIError, ask_portfolio_question


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask Mistral to analyze your Alpaca Paper portfolio (read-only)."
    )
    parser.add_argument("question", help="Your portfolio question in plain language.")
    args = parser.parse_args()

    if not os.environ.get("MISTRAL_API_KEY"):
        print("Missing MISTRAL_API_KEY Codespaces secret/environment variable.", file=sys.stderr)
        return 2

    key_id = os.environ.get("APCA_API_KEY_ID")
    secret_key = os.environ.get("APCA_API_SECRET_KEY")
    if not key_id or not secret_key:
        print(
            "Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY. "
            "Use Alpaca Paper Trading credentials.",
            file=sys.stderr,
        )
        return 2

    try:
        snapshot = build_snapshot(AlpacaReadOnlyClient(key_id, secret_key))
        answer = ask_portfolio_question(args.question, snapshot)
        print(answer)
        return 0
    except requests.RequestException as exc:
        print(f"Portfolio snapshot failed: network error ({type(exc).__name__}).", file=sys.stderr)
        return 1
    except (MistralAPIError, ValueError, RuntimeError) as exc:
        print(f"Portfolio analysis failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
