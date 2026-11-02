"""Deterministic news-to-held-position impact analysis; no trading actions."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def analyze_portfolio_impact(snapshot: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match archived events to held positions and estimate portfolio exposure."""
    account = snapshot.get("account") or {}
    equity = _decimal(account.get("equity") or account.get("portfolio_value"))
    positions = []
    grouped = snapshot.get("positions") or {}
    for key in ("long", "short", "options", "other"):
        positions.extend(grouped.get(key) or [])
    held: dict[str, dict[str, Any]] = {}
    for position in positions:
        symbol = str(position.get("symbol") or "").strip().upper()
        if symbol:
            held[symbol] = position

    results = []
    for event in events:
        symbols = {str(item).strip().upper() for item in (event.get("symbols") or []) if str(item).strip()}
        title = str(event.get("title") or "")
        summary = str(event.get("summary") or "")
        text = (title + " " + summary).lower()
        for symbol in sorted(symbols.intersection(held)):
            position = held[symbol]
            positive = [term for term in ("beats estimates", "raises guidance", "record revenue", "strong earnings", "approval", "upgrade", "contract") if term in text]
            negative = [term for term in ("misses estimates", "cuts guidance", "weak earnings", "investigation", "fraud", "bankruptcy", "default", "recall", "lawsuit", "downgrade", "going concern", "restatement") if term in text]
            if negative and not positive:
                impact, severity, reasons = "POTENTIAL_RISK", ("HIGH" if any(x in negative for x in ("fraud", "bankruptcy", "going concern", "default")) else "MEDIUM"), negative
            elif positive and not negative:
                impact, severity, reasons = "POTENTIAL_OPPORTUNITY", "MEDIUM", positive
            elif positive or negative:
                impact, severity, reasons = "MIXED_OR_UNCERTAIN", "LOW", positive + negative
            else:
                impact, severity, reasons = "NEUTRAL_OR_UNCLASSIFIED", "LOW", []
            market_value = _decimal(position.get("market_value"))
            exposure_pct = None
            if market_value is not None and equity is not None and equity > 0:
                exposure_pct = float(abs(market_value) / equity * Decimal("100"))
            identity = str(event.get("source_id") or event.get("canonical_url") or event.get("id") or title)
            key = hashlib.sha256(f"{symbol}|{identity}|{impact}".encode()).hexdigest()
            results.append({
                "impact_key": key, "symbol": symbol, "impact": impact, "severity": severity,
                "title": title or "Untitled archived event",
                "description": ("Matched to a currently held position. Signal terms: " + ", ".join(reasons) + ". " if reasons else "Matched by symbol; no configured directional terms were detected. ") +
                               "This is a keyword-based signal, not confirmation of financial impact.",
                "source_url": event.get("canonical_url"), "source": event.get("source"),
                "published_at": event.get("published_at"), "observed_at": event.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
                "market_value": str(market_value) if market_value is not None else None,
                "exposure_pct": round(exposure_pct, 2) if exposure_pct is not None else None,
                "evidence_terms": reasons, "confidence": "LOW" if impact in {"MIXED_OR_UNCERTAIN", "NEUTRAL_OR_UNCLASSIFIED"} else "KEYWORD_MATCH",
            })
    return sorted(results, key=lambda item: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[item["severity"]], item["symbol"], item["title"]))
