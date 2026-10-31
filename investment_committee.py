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
    technical = card.get("technical") or {}
    technical_score = technical.get("score")
    sentiment = card.get("sentiment") or {}
    sentiment_score = sentiment.get("score")
    fundamental_score = round(min(1.0, max(0.0, score / 100)), 4)
    analyst_scores = (technical_score, sentiment_score, fundamental_score)
    analysts_complete = (complete and not stale and all(isinstance(value, (int, float)) and 0 <= value <= 1 for value in analyst_scores))
    combined_score = round(sum(analyst_scores) / 3, 4) if analysts_complete else None
    hard_block = bool(risk_terms or severe_financial_risk
                      or (filing_age is not None and filing_age > 550)
                      or any("exceed 85%" in item for item in risks))
    decision = "DO_NOT_BUY" if hard_block else (
        "PAPER_BUY_CANDIDATE" if (
            analysts_complete and combined_score >= 0.70 and score >= 75
            and complete and not stale
        ) else ("RESEARCH_INCOMPLETE" if not analysts_complete else "DO_NOT_BUY")
    )
    if not analysts_complete:
        missing.append("technical or sentiment analyst score")

    return {
        "decision": decision,
        "score": min(100, score),
        "fundamental_score": fundamental_score,
        "technical_score": technical_score,
        "sentiment_score": sentiment_score,
        "combined_score": combined_score,
        "analysts_complete": analysts_complete,
        "weights": {"technical": 1/3, "sentiment": 1/3, "fundamental": 1/3},
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
            else ("Technical and sentiment analysis are not yet available; no buy candidate can be declared."
                  if not analysts_complete else
                  "Does not pass every required screening gate. Keep on watch or reject; do not buy in the simulation.")
        ),
        "disclaimer": "Educational screening only. No order is created or submitted.",
    }


def select_shortlist(cards: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Always show top discovered stocks; missing SEC data stays explicitly missing."""
    eligible = []
    for card in cards:
        reviewed = dict(card)
        reviewed["investment_review"] = review_stock(card)
        eligible.append(reviewed)
    eligible.sort(
        key=lambda item: (
            item["investment_review"]["analysts_complete"],
            item["investment_review"]["score"],
            float((item.get("market") or {}).get("daily_dollar_volume") or 0),
            float(item.get("discovery_score") or 0),
        ),
        reverse=True,
    )
    return eligible[:max(1, min(int(limit), 5))]
