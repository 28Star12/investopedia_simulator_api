"""Read-only technical indicators and two transparent entry-screening strategies."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

DATA_API = "https://data.alpaca.markets"
TIMEOUT = 20
BATCH_SIZE = 100


def _number(value: Any) -> float | None:
    try:
        result = float(value)
        return result if result == result and abs(result) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def analyze_bars(bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate SMA20/SMA50 and RSI14; identify reversal and trend setups."""
    closes = [_number(item.get("c")) for item in bars if isinstance(item, dict)]
    closes = [value for value in closes if value is not None and value > 0]
    if len(closes) < 50:
        return {
            "status": "INSUFFICIENT_DATA", "bars_available": len(closes),
            "required_bars": 50, "sma_20": None, "sma_50": None,
            "rsi_14": None, "reversal": {"status": "INSUFFICIENT_DATA"},
            "trend": {"status": "INSUFFICIENT_DATA"},
            "score": None, "signals": [],
        }

    sma20, sma50, rsi14 = _sma(closes, 20), _sma(closes, 50), _rsi(closes, 14)
    rising_two_days = closes[-1] > closes[-2] > closes[-3]
    recent_rsi = [_rsi(closes[:index], 14) for index in range(max(15, len(closes) - 5), len(closes) + 1)]
    recent_oversold = any(value is not None and value < 30 for value in recent_rsi)
    reversal = "NO_SETUP"
    if sma20 < sma50 and recent_oversold:
        reversal = "STABILIZING" if rising_two_days else "WAIT_FOR_STABILIZATION"
        if rising_two_days and closes[-1] > closes[-2]:
            reversal = "POTENTIAL_REVERSAL"
    trend = "NO_SETUP"
    if sma20 > sma50:
        trend = "BULLISH_TREND" if closes[-1] > sma20 and 40 <= (rsi14 or 0) <= 70 else "TREND_NEEDS_CONFIRMATION"

    signals = []
    if reversal == "POTENTIAL_REVERSAL":
        signals.append("REVERSAL_SETUP")
    elif reversal in {"WAIT_FOR_STABILIZATION", "STABILIZING"}:
        signals.append(reversal)
    if trend == "BULLISH_TREND":
        signals.append("BULLISH_TREND")
    elif trend == "TREND_NEEDS_CONFIRMATION":
        signals.append("TREND_NEEDS_CONFIRMATION")

    score = 0.5
    if sma20 > sma50:
        score += 0.20
    elif sma20 < sma50:
        score -= 0.05
    if rsi14 is not None:
        if 40 <= rsi14 <= 65:
            score += 0.15
        elif rsi14 > 70:
            score -= 0.10
        elif rsi14 < 30:
            score -= 0.05
    if reversal == "POTENTIAL_REVERSAL":
        score += 0.15
    if trend == "BULLISH_TREND":
        score += 0.15
    if closes[-1] < sma20:
        score -= 0.10
    score = round(max(0.0, min(1.0, score)), 4)

    return {
        "status": "AVAILABLE", "bars_available": len(closes), "required_bars": 50,
        "latest_close": round(closes[-1], 4), "sma_20": round(sma20, 4),
        "sma_50": round(sma50, 4), "rsi_14": round(rsi14, 2) if rsi14 is not None else None,
        "reversal": {"status": reversal, "oversold_recently": recent_oversold,
                     "two_consecutive_higher_closes": rising_two_days},
        "trend": {"status": trend, "price_above_sma20": closes[-1] > sma20},
        "score": score, "signals": signals,
        "method": "SMA20_SMA50_RSI14_v1",
        "note": "Indicators are screening signals, not forecasts or trade instructions.",
    }


class AlpacaTechnicalAnalyzer:
    """Fetch daily bars from Alpaca using GET-only market-data requests."""

    def __init__(self, key_id: str, secret_key: str, session: Any = None):
        if not key_id or not secret_key:
            raise ValueError("Alpaca API credentials are required.")
        self.session = session or requests.Session()
        self.headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key,
                        "Accept": "application/json"}

    def collect(self, symbols: list[str], lookback_days: int = 120) -> dict[str, dict]:
        unique = sorted({str(symbol).upper() for symbol in symbols if symbol})
        results: dict[str, dict] = {}
        start = (datetime.now(timezone.utc) - timedelta(days=max(90, lookback_days))).isoformat().replace("+00:00", "Z")
        for offset in range(0, len(unique), BATCH_SIZE):
            batch = unique[offset:offset + BATCH_SIZE]
            response = self.session.get(
                DATA_API + "/v2/stocks/bars",
                headers=self.headers,
                params={"symbols": ",".join(batch), "timeframe": "1Day",
                        "start": start, "limit": 1000, "adjustment": "split", "feed": "iex"},
                timeout=TIMEOUT,
            )
            if not response.ok:
                for symbol in batch:
                    results[symbol] = {"status": "FETCH_ERROR", "error": f"HTTP {response.status_code}"}
                continue
            payload = response.json()
            bars_by_symbol = payload.get("bars", {}) if isinstance(payload, dict) else {}
            for symbol in batch:
                results[symbol] = analyze_bars(bars_by_symbol.get(symbol, []))
        return results
