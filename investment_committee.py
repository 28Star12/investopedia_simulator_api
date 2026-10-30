"""Conservative five-stock research committee; recommendations only, never trades."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

CORE_METRICS = ("revenue", "operating_income", "net_income", "operating_cash_flow")


def _metric(fundamentals: dict[str, Any], name: str) -> float | None:
    item = (fundamentals.get("metrics") or {}).get(name)
    if not isinstance(item, dict):
        return None
    try:
        value = float(item.get("value"))
        return value if value == value and abs(value) != float("inf") else None
    except (TypeError, ValueError):
        return None


def _filing_age_days(fundamentals: dict[str, Any]) -> int | None:
    dates = []
    for item in (fundamentals.get("metrics") or {}).values():
        if not isinstance(item, dict):
            continue
        raw = item.get("filed") or item.get("period_end")
        try:
            dates.append(date.fromisoformat(str(raw)[:10]))
        except (TypeError, ValueError):
            continue
    if not dates:
        return None
    return max(0, (datetime.now(timezone.utc).date() - min(dates)).days)


def review_stock(card: dict[str, Any]) -> dict[str, Any]:
    fundamentals = card.get("fundamentals") or {}
    metrics = {name: _metric(fundamentals, name) for name in CORE_METRICS}
    ratios = fundamentals.get("ratios") or {}
    score = 0
    reasons: list[str] = []
    risks: list[str] = []
    missing = [name for name, value in metrics.items() if value is None]

    checks = (
        ("revenue", 15, "Annual revenue is positive", "Annual revenue is not positive"),
        ("operating_income", 20, "Operating income is positive", "Operating income is not positive"),
        ("net_income", 20, "Net income is positive", "Net income is not positive"),
        ("operating_cash_flow", 20, "Operating cash flow is positive", "Operating cash flow is not positive"),
    )
    for name, points, positive_reason, risk_reason in checks:
        value = metrics[name]
        if value is not None:
            if value > 0:
                score += points
                reasons.append(positive_reason)
            else:
                risks.append(risk_reason)

    op_margin = ratios.get("operating_margin")
    net_margin = ratios.get("net_margin")
    leverage = ratios.get("liabilities_to_assets")
    if isinstance(op_margin, (int, float)):
        if op_margin >= 0.10:
            score += 8
            reasons.append("Operating margin is at least 10%")
        elif op_margin > 0:
            score += 4
        else:
            risks.append("Operating margin is not positive")
    if isinstance(net_margin, (int, float)):
        if net_margin >= 0.05:
            score += 7
            reasons.append("Net margin is at least 5%")
        elif net_margin > 0:
            score += 3
        else:
            risks.append("Net margin is not positive")
    if isinstance(leverage, (int, float)):
        if leverage < 0.60:
            score += 10
            reasons.append("Liabilities are below 60% of assets")
        elif leverage <= 0.85:
            score += 5
        else:
            risks.append("Liabilities exceed 85% of assets")
    else:
        missing.append("liabilities_to_assets ratio")

    news_score = int(card.get("news_score_heuristic") or 0)
    risk_terms = list(card.get("risk_terms") or [])
    if news_score >= 2 and not risk_terms:
        score += 5
        reasons.append("Recent archived news signal is positive")
    if risk_terms:
        risks.append("Negative news keywords: " + ", ".join(risk_terms[:5]))
    elif news_score <= -2:
        risks.append("Recent archived news signal is negative")

    try:
        dollar_volume = float((card.get("market") or {}).get("daily_dollar_volume") or 0)
    except (TypeError, ValueError):
        dollar_volume = 0
    if dollar_volume >= 10_000_000:
        score += 5
        reasons.append("Daily dollar volume exceeds $10 million")
    elif dollar_volume < 1_000_000:
        risks.append("Daily dollar volume is below the screening threshold")

    filing_age = _filing_age_days(fundamentals)
    stale = filing_age is None or filing_age > 550
    if stale:
        risks.append("Annual SEC filing data is missing or older than 550 days")
    complete = not missing and fundamentals.get("status") == "AVAILABLE"
    severe_financial_risk = any(metrics[name] is not None and metrics[name] <= 0
                                for name in ("operating_income", "net_income", "operating_cash_flow"))
    decision = "PAPER_BUY_CANDIDATE" if (
        score >= 75 and complete and not stale and not risk_terms
        and not severe_financial_risk and not any("exceed 85%" in x for x in risks)
    ) else "DO_NOT_BUY"

    return {
        "decision": decision,
        "score": min(100, score),
        "reasons": reasons,
        "risks": risks,
        "missing_data": missing,
        "annual_filing_age_days": filing_age,
        "data_complete": complete,
        "method": "conservative_rules_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "explanation": (
            "Passes the conservative paper-buy screening rules; this is a research candidate, not an order."
            if decision == "PAPER_BUY_CANDIDATE"
            else "Does not pass every required screening gate. Keep on watch or reject; do not buy in the simulation."
        ),
        "disclaimer": "Educational screening only. No order is created or submitted.",
    }


def select_shortlist(cards: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Return up to five companies with usable core annual SEC fundamentals."""
    eligible = []
    for card in cards:
        fundamentals = card.get("fundamentals") or {}
        available = sum(_metric(fundamentals, name) is not None for name in CORE_METRICS)
        if available >= 3:
            reviewed = dict(card)
            reviewed["investment_review"] = review_stock(card)
            eligible.append(reviewed)
    eligible.sort(
        key=lambda item: (
            item["investment_review"]["score"],
            item["investment_review"]["decision"] == "PAPER_BUY_CANDIDATE",
            float((item.get("market") or {}).get("daily_dollar_volume") or 0),
        ),
        reverse=True,
    )
    selected = eligible[:max(1, min(int(limit), 5))]
    return selected
