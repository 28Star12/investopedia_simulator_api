"""Read-only SEC XBRL fundamentals collector."""
from __future__ import annotations
import re
from typing import Any
import requests

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
TIMEOUT = 25
MAX_BYTES = 30_000_000

# GAAP concepts, in priority order. We select the latest annual fact for comparability.
CONCEPTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "long_term_debt": ("LongTermDebtCurrent", "LongTermDebtNoncurrent", "LongTermDebt"),
    "eps": ("EarningsPerShareDiluted",),
}

class SECCompanyFacts:
    def __init__(self, user_agent: str, session: Any = None):
        if not user_agent or len(user_agent.strip()) < 8 or "\n" in user_agent or "\r" in user_agent:
            raise ValueError("Set SEC_USER_AGENT to an identifying value with a valid contact.")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent.strip(), "Accept-Encoding": "gzip, deflate", "Accept": "application/json"})

    def _json(self, url: str) -> dict:
        response = self.session.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        if len(response.content) > MAX_BYTES:
            raise ValueError("SEC company facts response is too large.")
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected SEC JSON response.")
        return data

    def ticker_map(self) -> dict[str, str]:
        payload = self._json(TICKERS_URL)
        return {str(x["ticker"]).upper(): str(x["cik_str"]).zfill(10)
                for x in payload.values() if isinstance(x, dict)
                and re.fullmatch(r"[A-Z0-9.-]{1,12}", str(x.get("ticker", "")))
                and isinstance(x.get("cik_str"), int)}

    @staticmethod
    def _latest_annual(units: dict) -> dict | None:
        rows = [x for x in units if isinstance(x, dict) and x.get("form") in {"10-K", "20-F"}
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(x.get("end", "")))
                and isinstance(x.get("val"), (int, float))]
        rows.sort(key=lambda x: (x["end"], x.get("filed", "")), reverse=True)
        return rows[0] if rows else None

    def fetch_symbol(self, symbol: str, cik: str) -> dict:
        payload = self._json(FACTS_URL.format(cik=cik))
        facts = payload.get("facts", {}).get("us-gaap", {})
        values, dates = {}, {}
        for metric, concepts in CONCEPTS.items():
            found = None
            for concept in concepts:
                node = facts.get(concept, {})
                for unit, rows in node.get("units", {}).items():
                    candidate = self._latest_annual(rows)
                    if candidate:
                        found = (candidate, unit)
                        break
                if found:
                    break
            if found:
                row, unit = found
                values[metric] = {"value": row["val"], "unit": unit, "period_end": row["end"], "filed": row.get("filed")}
                dates[metric] = row["end"]
        revenue = values.get("revenue", {}).get("value")
        operating = values.get("operating_income", {}).get("value")
        net = values.get("net_income", {}).get("value")
        assets = values.get("assets", {}).get("value")
        liabilities = values.get("liabilities", {}).get("value")
        cashflow = values.get("operating_cash_flow", {}).get("value")
        debt = values.get("long_term_debt", {}).get("value")
        ratios = {}
        if revenue and operating is not None: ratios["operating_margin"] = operating / revenue
        if revenue and net is not None: ratios["net_margin"] = net / revenue
        if assets and liabilities is not None: ratios["liabilities_to_assets"] = liabilities / assets
        if revenue and cashflow is not None: ratios["operating_cash_flow_to_revenue"] = cashflow / revenue
        if revenue and debt is not None: ratios["debt_to_revenue"] = debt / revenue
        return {"symbol": symbol, "cik": cik, "status": "AVAILABLE" if values else "NO_XBRL_FACTS",
                "metrics": values, "ratios": ratios,
                "period_note": "Latest available annual SEC facts; metrics may have different fiscal period ends.",
                "source_url": FACTS_URL.format(cik=cik)}

    def collect(self, symbols: list[str]) -> dict[str, dict]:
        mapping = self.ticker_map()
        output = {}
        for symbol in sorted(set(s.upper() for s in symbols)):
            if not re.fullmatch(r"[A-Z0-9.-]{1,12}", symbol):
                continue
            cik = mapping.get(symbol)
            if not cik:
                output[symbol] = {"symbol": symbol, "status": "TICKER_NOT_FOUND"}
                continue
            try:
                output[symbol] = self.fetch_symbol(symbol, cik)
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                output[symbol] = {"symbol": symbol, "status": "FETCH_ERROR", "error": str(exc)[:240]}
        return output
