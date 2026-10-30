"""Explainable, conservative research classification; never submits orders."""
from __future__ import annotations

def classify_research(card: dict) -> dict:
    points, reasons, risks, missing = 0, [], [], []
    fundamentals = card.get("fundamentals") or {}
    metrics, ratios = fundamentals.get("metrics") or {}, fundamentals.get("ratios") or {}
    def value(name):
        item = metrics.get(name)
        return item.get("value") if isinstance(item, dict) else None
    revenue, operating, net = value("revenue"), value("operating_income"), value("net_income")
    cashflow, assets, liabilities = value("operating_cash_flow"), value("assets"), value("liabilities")
    if revenue is None: missing.append("annual revenue")
    elif revenue > 0: points += 1; reasons.append("positive annual revenue")
    else: risks.append("non-positive annual revenue")
    if operating is None: missing.append("operating income")
    elif operating > 0: points += 2; reasons.append("positive operating income")
    else: points -= 2; risks.append("negative operating income")
    if net is None: missing.append("net income")
    elif net > 0: points += 2; reasons.append("positive net income")
    else: points -= 2; risks.append("negative net income")
    if cashflow is None: missing.append("operating cash flow")
    elif cashflow > 0: points += 2; reasons.append("positive operating cash flow")
    else: points -= 2; risks.append("negative operating cash flow")
    leverage = ratios.get("liabilities_to_assets")
    if leverage is None: missing.append("liabilities/assets ratio")
    elif leverage > 0.85: points -= 2; risks.append("high liabilities relative to assets")
    elif leverage < 0.60: points += 1; reasons.append("moderate liabilities relative to assets")
    news_score = int(card.get("news_score_heuristic") or 0)
    if news_score >= 3 and not card.get("risk_terms"): points += 1; reasons.append("positive keyword-based news signal")
    if news_score <= -3 or card.get("risk_terms"): points -= 2; risks.append("negative keyword-based news signal")
    # A candidate requires sufficient coverage and no material risk flag.
    covered = len(metrics) >= 4
    if not covered:
        decision = "WATCH"
        explanation = "Insufficient SEC fundamental coverage for a candidate classification."
    elif points >= 5 and not risks:
        decision = "CANDIDATE"
        explanation = "Fundamentals and available news pass the conservative screening thresholds."
    elif points <= -2 or (operating is not None and operating < 0 and net is not None and net < 0):
        decision = "AVOID"
        explanation = "Material financial or news risks triggered the conservative screening threshold."
    else:
        decision = "WATCH"
        explanation = "Mixed signals or unresolved risks; monitor for new filings and results."
    return {"decision": decision, "score": points, "reasons": reasons, "risks": risks,
            "missing_data": missing, "explanation": explanation,
            "method": "deterministic_screen_v1",
            "disclaimer": "Research screening only; not personalized financial advice and never an instruction to trade."}
