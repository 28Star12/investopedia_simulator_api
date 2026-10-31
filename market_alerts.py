"""Deterministic, deduplicated market alerts. No trading endpoints."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from typing import Any

RISK_TERMS = ("fraud", "bankruptcy", "default", "going concern", "restatement",
              "cuts guidance", "misses estimates", "investigation", "recall")
POSITIVE_TERMS = ("beats estimates", "raises guidance", "record revenue",
                  "strong earnings", "major contract", "raises outlook")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

def generate_alerts(candidates: list[dict[str, Any]], events: list[dict[str, Any]],
                    now: str | None = None) -> list[dict[str, Any]]:
    """Alert on >=3% daily moves, material news terms, and archived SEC filings."""
    observed = now or _now()
    day = observed[:10]
    alerts = []
    for item in candidates:
        symbol = str(item.get("symbol") or "").strip().upper()
        try:
            change = float(item.get("change_pct"))
        except (TypeError, ValueError):
            continue
        if not symbol or abs(change) < 3:
            continue
        severity = "HIGH" if abs(change) >= 5 else "MEDIUM"
        alerts.append({
            "alert_key": _key("price", symbol, day), "symbol": symbol,
            "alert_type": "price_move", "severity": severity,
            "title": f"{symbol}: unusually large daily move ({change:+.2f}%)",
            "description": f"{symbol} moved {change:+.2f}% in the available daily market snapshot. This is a movement signal, not an explanation or forecast.",
            "observed_at": observed,
            "payload": {"change_pct": change, "price": item.get("price"),
                        "feed": item.get("data_feed")},
        })
    for event in events:
        event_type = str(event.get("event_type") or "news")
        title = str(event.get("title") or "")
        text = (title + " " + str(event.get("summary") or "")).lower()
        for raw_symbol in event.get("symbols") or []:
            symbol = str(raw_symbol).strip().upper()
            if not symbol:
                continue
            if event_type == "sec_filing":
                form = str((event.get("metadata") or {}).get("form") or "SEC")
                severity, alert_type = ("HIGH" if form == "8-K" else "MEDIUM"), "sec_filing"
                headline = f"{symbol}: new SEC filing ({form})"
                description = f"A new {form} filing for {symbol} was archived. A filing is not inherently positive or negative; review the official document."
            elif event_type == "news":
                risk = [term for term in RISK_TERMS if term in text]
                positive = [term for term in POSITIVE_TERMS if term in text]
                if risk:
                    severity, alert_type = "HIGH", "negative_news"
                    headline = f"{symbol}: risk-related news signal"
                    description = "Archived headline/summary contains: " + ", ".join(risk) + ". Verify the source."
                elif positive:
                    severity, alert_type = "MEDIUM", "positive_news"
                    headline = f"{symbol}: potentially positive news signal"
                    description = "Archived headline/summary contains: " + ", ".join(positive) + ". Verify the source."
                else:
                    continue
            else:
                continue
            identity = str(event.get("source_id") or event.get("canonical_url") or event.get("id") or title)
            alerts.append({
                "alert_key": _key(event_type, symbol, identity, alert_type),
                "symbol": symbol, "alert_type": alert_type, "severity": severity,
                "title": headline, "description": description,
                "source_url": event.get("canonical_url"),
                "observed_at": event.get("published_at") or event.get("fetched_at") or observed,
                "payload": {"source": event.get("source"), "source_title": title},
            })
    return alerts
