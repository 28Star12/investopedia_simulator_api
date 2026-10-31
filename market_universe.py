"""Autonomous US-equity discovery using Alpaca's public-to-account GET endpoints.

The module discovers active assets itself, screens them with market snapshots,
and returns a ranked research shortlist. It never submits or changes orders.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

import requests

PAPER_API = "https://paper-api.alpaca.markets"
DATA_API = "https://data.alpaca.markets"
TIMEOUT = 20
BATCH_SIZE = 100


def _decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


class AlpacaMarketDiscovery:
    """Find liquid active US equities without a user-supplied ticker list."""

    def __init__(self, key_id: str, secret_key: str, session: Any = None):
        if not key_id or not secret_key:
            raise ValueError("Alpaca Paper Trading API credentials are required.")
        self.session = session or requests.Session()
        self.headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }

    def _get(self, base: str, path: str, params: dict | None = None) -> Any:
        if base not in {PAPER_API, DATA_API} or not path.startswith("/v2/") or "://" in path:
            raise ValueError("Only fixed Alpaca GET endpoints are allowed.")
        response = self.session.get(
            base + path, headers=self.headers, params=params, timeout=TIMEOUT
        )
        if not response.ok:
            raise RuntimeError(f"Alpaca market discovery returned HTTP {response.status_code}.")
        return response.json()

    def discover_assets(self) -> list[dict]:
        payload = self._get(
            PAPER_API, "/v2/assets",
            {"status": "active", "asset_class": "us_equity"},
        )
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected Alpaca assets response.")
        assets = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip().upper()
            if (
                item.get("status") == "active"
                and item.get("tradable") is True
                and item.get("class") == "us_equity"
                and symbol
                and len(symbol) <= 12
                and all(ch.isalnum() or ch in ".-" for ch in symbol)
            ):
                attributes = item.get("attributes") or []
                if isinstance(attributes, list) and any("etf" in str(a).lower() for a in attributes):
                    continue
                assets.append({
                    "symbol": symbol,
                    "name": str(item.get("name") or symbol)[:160],
                    "exchange": str(item.get("exchange") or "unknown"),
                })
        return sorted(assets, key=lambda item: item["symbol"])

    def snapshots(self, symbols: Iterable[str]) -> dict[str, dict]:
        unique = sorted(set(symbols))
        result: dict[str, dict] = {}
        for start in range(0, len(unique), BATCH_SIZE):
            batch = unique[start:start + BATCH_SIZE]
            payload = self._get(
                DATA_API, "/v2/stocks/snapshots",
                {"symbols": ",".join(batch), "feed": "iex"},
            )
            if isinstance(payload, dict):
                for symbol, snapshot in payload.items():
                    if isinstance(snapshot, dict):
                        result[str(symbol).upper()] = snapshot
        return result

    @staticmethod
    def rank_assets(assets: list[dict], snapshots: dict[str, dict],
                    min_price: Decimal = Decimal("5"),
                    min_dollar_volume: Decimal = Decimal("1000000"),
                    limit: int = 100) -> list[dict]:
        ranked = []
        for asset in assets:
            symbol = asset["symbol"]
            snap = snapshots.get(symbol)
            if not isinstance(snap, dict):
                continue
            daily = snap.get("dailyBar") or {}
            previous = snap.get("prevDailyBar") or {}
            latest_trade = snap.get("latestTrade") or {}
            price = _decimal(latest_trade.get("p")) or _decimal(daily.get("c"))
            volume = _decimal(daily.get("v"))
            previous_close = _decimal(previous.get("c"))
            if price is None or volume is None or price < min_price or volume <= 0:
                continue
            dollar_volume = price * volume
            if dollar_volume < min_dollar_volume:
                continue
            change_pct = None
            if previous_close is not None and previous_close > 0:
                change_pct = (price - previous_close) / previous_close * Decimal("100")
            # Transparent screening score: liquidity dominates; movement is a
            # secondary discovery signal, not a buy signal.
            liquidity_score = min(float(dollar_volume / Decimal("10000000")), 100.0)
            movement_score = min(float(abs(change_pct or Decimal("0"))), 20.0)
            score = liquidity_score * 0.8 + movement_score * 0.2
            ranked.append({
                **asset,
                "price": str(price),
                "volume": str(volume),
                "dollar_volume": str(dollar_volume.quantize(Decimal("0.01"))),
                "change_pct": str(change_pct.quantize(Decimal("0.01"))) if change_pct is not None else None,
                "discovery_score": round(score, 4),
                "screen": "liquidity_and_activity",
                "data_feed": "IEX",
            })
        ranked.sort(key=lambda row: (row["discovery_score"], Decimal(row["dollar_volume"])), reverse=True)
        return ranked[:max(1, min(int(limit), 500))]

    def run(self, limit: int = 100, min_price: str = "5",
            min_dollar_volume: str = "1000000") -> dict:
        assets = self.discover_assets()
        snapshots = self.snapshots(asset["symbol"] for asset in assets)
        candidates = self.rank_assets(
            assets, snapshots, _decimal(min_price) or Decimal("5"),
            _decimal(min_dollar_volume) or Decimal("1000000"), limit,
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "universe": "Alpaca active tradable US equities (ETFs excluded when identified)",
            "assets_discovered": len(assets),
            "assets_with_snapshots": len(snapshots),
            "candidates": candidates,
            "candidate_count": len(candidates),
            "feed": "IEX",
            "data_quality_note": "IEX-only snapshots may be incomplete versus consolidated US market data; missing snapshots are excluded.",
            "read_only": True,
            "orders_submitted": 0,
            "http_methods_used": ["GET"],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover and rank US stocks automatically (read-only).")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--min-price", default="5")
    parser.add_argument("--min-dollar-volume", default="1000000")
    args = parser.parse_args()
    key = os.environ.get("APCA_API_KEY_ID")
    secret = os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        parser.error("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY locally; never paste them into chat.")
    result = AlpacaMarketDiscovery(key, secret).run(args.limit, args.min_price, args.min_dollar_volume)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
