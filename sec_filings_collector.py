"""Read-only collector for official SEC EDGAR company filings."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests

from market_event_store import MarketEventStore

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
ALLOWED_FORMS = {"8-K", "10-K", "10-Q", "20-F", "6-K", "S-1", "S-3", "DEF 14A"}
MAX_RESPONSE_BYTES = 12_000_000
TIMEOUT_SECONDS = 20


def _response_json(response: Any) -> dict:
    response.raise_for_status()
    content = response.content
    if len(content) > MAX_RESPONSE_BYTES:
        raise ValueError("SEC response exceeds the configured size limit.")
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected SEC JSON response.")
    return data


def _clean_symbol(value: str) -> str:
    symbol = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9.\\-]{1,12}", symbol):
        raise ValueError(f"Invalid ticker symbol: {value!r}")
    return symbol


class SECFilingsCollector:
    """Fetch company identifiers and recent filings from SEC's public JSON APIs."""

    def __init__(self, user_agent: str, session: Any = None, timeout: int = TIMEOUT_SECONDS):
        if not user_agent or len(user_agent.strip()) < 8 or "\\n" in user_agent or "\\r" in user_agent:
            raise ValueError("Set SEC_USER_AGENT to an identifying value with a valid contact, e.g. an email address.")
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent.strip(),
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        })
        self.timeout = timeout

    def _get_json(self, url: str) -> dict:
        response = self.session.get(url, timeout=self.timeout)
        return _response_json(response)

    def ticker_map(self) -> dict[str, str]:
        payload = self._get_json(TICKERS_URL)
        mapping = {}
        for item in payload.values():
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker", "")).upper()
            cik = item.get("cik_str")
            if re.fullmatch(r"[A-Z0-9.\\-]{1,12}", ticker) and isinstance(cik, int):
                mapping[ticker] = str(cik).zfill(10)
        return mapping

    def collect_symbol(self, symbol: str, cik: str, store: MarketEventStore, limit: int = 20) -> dict:
        payload = self._get_json(SUBMISSIONS_URL.format(cik=cik))
        recent = payload.get("filings", {}).get("recent", {})
        fields = ("accessionNumber", "filingDate", "form", "primaryDocument", "primaryDocDescription")
        arrays = [recent.get(field, []) for field in fields]
        if not all(isinstance(values, list) for values in arrays):
            raise ValueError("SEC submissions response has invalid recent-filings fields.")
        events = []
        for values in zip(*arrays):
            accession, filing_date, form, document, description = values
            if form not in ALLOWED_FORMS:
                continue
            if not re.fullmatch(r"\\d{10}-\\d{2}-\\d{6}", str(accession)):
                continue
            if not re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", str(filing_date)):
                continue
            document = str(document or "")
            if not document or document.startswith("/") or ".." in document or "://" in document:
                continue
            accession_path = str(accession).replace("-", "")
            url = ARCHIVE_URL.format(cik=int(cik), accession=accession_path, document=document)
            title = f"{symbol}: SEC Form {form} filed {filing_date}"
            if description:
                title += f" — {str(description)[:180]}"
            events.append({
                "source": "sec_edgar",
                "source_id": str(accession),
                "url": url,
                "title": title,
                "summary": f"Official SEC filing: {form}. Company CIK: {cik}.",
                "published_at": filing_date + "T00:00:00+00:00",
                "symbols": [symbol],
                "event_type": "sec_filing",
                "metadata": {"form": form, "cik": cik, "accession": accession, "document": document},
            })
            if len(events) >= max(1, min(int(limit), 100)):
                break
        saved = store.add_events(events)
        return {"symbol": symbol, "cik": cik, "fetched": len(events), "stored": len(saved), "error": None}

    def collect(self, symbols: list[str], store: MarketEventStore, limit: int = 20) -> dict:
        mapping = self.ticker_map()
        results = []
        for raw in symbols:
            try:
                symbol = _clean_symbol(raw)
                cik = mapping.get(symbol)
                if not cik:
                    results.append({"symbol": symbol, "fetched": 0, "stored": 0, "error": "Ticker not found in SEC company_tickers.json."})
                    continue
                results.append(self.collect_symbol(symbol, cik, store, limit))
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                results.append({"symbol": str(raw)[:12], "fetched": 0, "stored": 0, "error": str(exc)[:300]})
        return {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "sources": results,
            "stored_total": sum(item["stored"] for item in results),
            "read_only": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect official SEC filings for ticker symbols.")
    parser.add_argument("--symbols", default=os.environ.get("WATCHLIST_SYMBOLS", ""), help="Comma-separated symbols, e.g. AAPL,MSFT")
    parser.add_argument("--limit", type=int, default=20, help="Maximum recent supported filings per symbol (1-100)")
    parser.add_argument("--db", default=os.environ.get("MARKET_EVENT_DB", "data/market_events.sqlite3"))
    args = parser.parse_args()
    user_agent = os.environ.get("SEC_USER_AGENT")
    if not user_agent:
        parser.error("Set SEC_USER_AGENT to an identifying value with a valid contact before using SEC EDGAR.")
    symbols = [part.strip() for part in args.symbols.split(",") if part.strip()]
    if not symbols:
        parser.error("Provide --symbols or WATCHLIST_SYMBOLS.")
    result = SECFilingsCollector(user_agent).collect(symbols, MarketEventStore(args.db), args.limit)
    for item in result["sources"]:
        print(f"{item['symbol']}: {item['stored']} filings saved" + (f" — {item['error']}" if item["error"] else ""))
    print(f"Total saved: {result['stored_total']} (read-only)")
    return 0 if all(item["error"] is None for item in result["sources"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
