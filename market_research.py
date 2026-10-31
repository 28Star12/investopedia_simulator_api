"""Second-stage research: collect ticker-linked news and build explainable research cards.

This is deterministic screening, not an LLM or a buy instruction. It uses Alpaca
news plus already archived SEC filing metadata, and remains GET-only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import requests

from market_event_store import MarketEventStore
from market_universe import AlpacaMarketDiscovery
from sec_company_facts import SECCompanyFacts
from decision_engine import classify_research
from market_alerts import generate_alerts
from market_news_collector import collect_feeds
from sec_filings_collector import SECFilingsCollector
from alpaca_readonly_agent import AlpacaReadOnlyClient, build_snapshot
from portfolio_impact import analyze_portfolio_impact
from investment_committee import select_shortlist
from technical_analysis import AlpacaTechnicalAnalyzer
from earnings_calendar import collect_earnings_calendar

DATA_API = "https://data.alpaca.markets"
TIMEOUT = 20
NEWS_BATCH = 50

POSITIVE_TERMS = {
    "beats estimates": 3, "raises guidance": 3, "record revenue": 2,
    "strong earnings": 2, "upgrade": 1, "contract": 1, "growth": 1,
    "profit": 1, "partnership": 1, "approval": 1,
}
NEGATIVE_TERMS = {
    "misses estimates": -3, "cuts guidance": -3, "weak earnings": -2,
    "investigation": -2, "fraud": -4, "bankruptcy": -5, "default": -4,
    "recall": -2, "lawsuit": -1, "downgrade": -1, "layoffs": -1,
    "going concern": -5, "restatement": -3,
}


def _clean_summary(value: Any, limit: int = 6000) -> str | None:
    if value is None:
        return None
    return " ".join(str(value).split())[:limit] or None


def _terms_score(text: str) -> tuple[int, list[str], list[str]]:
    lower = text.lower()
    score = 0
    positive, negative = [], []
    for term, points in POSITIVE_TERMS.items():
        if term in lower:
            score += points
            positive.append(term)
    for term, points in NEGATIVE_TERMS.items():
        if term in lower:
            score += points
            negative.append(term)
    return max(-10, min(10, score)), positive, negative


class AlpacaNewsCollector:
    def __init__(self, key_id: str, secret_key: str, session: Any = None):
        if not key_id or not secret_key:
            raise ValueError("Alpaca API credentials are required.")
        self.session = session or requests.Session()
        self.headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret_key,
            "Accept": "application/json",
        }

    def collect(self, symbols: list[str], store: MarketEventStore,
                limit_per_batch: int = 50) -> dict:
        unique = sorted(set(symbols))
        results = []
        for start in range(0, len(unique), NEWS_BATCH):
            batch = unique[start:start + NEWS_BATCH]
            try:
                response = self.session.get(
                    DATA_API + "/v1beta1/news",
                    headers=self.headers,
                    params={"symbols": ",".join(batch), "limit": max(1, min(limit_per_batch, 50)),
                            "sort": "desc", "include_content": "false"},
                    timeout=TIMEOUT,
                )
                if not response.ok:
                    raise RuntimeError(f"Alpaca news returned HTTP {response.status_code}.")
                payload = response.json()
                articles = payload.get("news", []) if isinstance(payload, dict) else []
                saved = 0
                for article in articles:
                    if not isinstance(article, dict) or not article.get("headline"):
                        continue
                    symbols_for_article = [
                        str(s).upper() for s in article.get("symbols", [])
                        if str(s).upper() in batch
                    ]
                    if not symbols_for_article:
                        continue
                    result = store.add_event({
                        "source": "alpaca_news",
                        "source_id": str(article.get("id") or article.get("url") or article["headline"]),
                        "url": article.get("url"),
                        "title": article["headline"],
                        "summary": _clean_summary(article.get("summary")),
                        "published_at": article.get("created_at"),
                        "symbols": symbols_for_article,
                        "event_type": "news",
                        "metadata": {
                            "author": str(article.get("author") or "")[:160],
                            "images_count": len(article.get("images") or []),
                            "provider": "Alpaca News API",
                        },
                    })
                    saved += 1
                results.append({"symbols": batch, "fetched": len(articles), "stored": saved, "error": None})
            except (requests.RequestException, RuntimeError, ValueError, TypeError) as exc:
                results.append({"symbols": batch, "fetched": 0, "stored": 0, "error": str(exc)[:240]})
        return {"batches": results, "stored_total": sum(x["stored"] for x in results)}


def _news_sentiment(events: list[dict[str, Any]], now: datetime | None = None,
                    max_age_days: int = 14) -> dict[str, Any]:
    """Estimate recent news tone; older/undated items cannot influence current sentiment."""
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    scored = []
    positive_count = negative_count = mixed_count = undated_count = stale_count = 0
    for event in events[:100]:
        raw_date = event.get("published_at") or event.get("fetched_at")
        try:
            published = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (observed - published.astimezone(timezone.utc)).total_seconds() / 86400)
        except (TypeError, ValueError):
            undated_count += 1
            continue
        if age_days > max_age_days:
            stale_count += 1
            continue
        score, positive, negative = _terms_score(
            (event.get("title") or "") + " " + (event.get("summary") or "")
        )
        # Exponential decay: recent headlines count more, with a 3.5-day half-life.
        weight = 0.5 ** (age_days / 3.5)
        scored.append((score, weight))
        if positive and negative:
            mixed_count += 1
        elif positive:
            positive_count += 1
        elif negative:
            negative_count += 1
    if not scored:
        return {
            "status": "NO_NEWS" if not events else "NO_RECENT_NEWS",
            "score": None, "direction_score": None,
            "extreme_score": None, "mood": "INSUFFICIENT_DATA",
            "positive_articles": 0, "negative_articles": 0,
            "neutral_or_mixed_articles": 0, "articles_analyzed": 0,
            "stale_articles_excluded": stale_count,
            "undated_articles_excluded": undated_count,
            "max_age_days": max_age_days,
            "source": "archived news headlines and summaries",
            "note": "No dated news within the recency window; sentiment is not inferred.",
        }
    total_weight = sum(weight for _, weight in scored)
    average = sum(score * weight for score, weight in scored) / total_weight
    direction = round(max(0.0, min(1.0, 0.5 + average / 20.0)), 4)
    extreme = round(sum(abs(score) * weight for score, weight in scored) / (10.0 * total_weight), 4)
    if extreme >= 0.65 and direction >= 0.75:
        mood = "CROWDED_OPTIMISM"
    elif extreme >= 0.65 and direction <= 0.25:
        mood = "PANIC_OR_HIGH_RISK"
    elif positive_count and negative_count:
        mood = "MIXED"
    elif direction > 0.60:
        mood = "POSITIVE"
    elif direction < 0.40:
        mood = "NEGATIVE"
    else:
        mood = "NEUTRAL"
    return {
        "status": "AVAILABLE", "score": direction,
        "direction_score": direction, "extreme_score": extreme,
        "mood": mood, "positive_articles": positive_count,
        "negative_articles": negative_count,
        "neutral_or_mixed_articles": mixed_count,
        "articles_analyzed": len(scored),
        "stale_articles_excluded": stale_count,
        "undated_articles_excluded": undated_count,
        "max_age_days": max_age_days,
        "source": "archived news headlines and summaries",
        "method": "recency_weighted_news_keyword_tone_v2",
        "note": "News tone is a proxy, not a survey of investors. Older items decay exponentially and items beyond the recency window are excluded.",
    }


def build_research_cards(candidates: list[dict], store: MarketEventStore,
                         limit: int = 100, fundamentals_by_symbol: dict | None = None,
                         technical_by_symbol: dict | None = None) -> list[dict]:
    cards = []
    fundamentals_by_symbol = fundamentals_by_symbol or {}
    technical_by_symbol = technical_by_symbol or {}
    for candidate in candidates[:max(1, min(limit, 500))]:
        symbol = candidate["symbol"]
        events = store.list_events(limit=250, symbol=symbol)
        relevant = [
            event for event in events
            if symbol in event.get("symbols", [])
        ]
        news_events = [event for event in relevant if event["event_type"] == "news"]
        sec_events = [event for event in relevant if event["event_type"] == "sec_filing"]
        news_score = 0
        positives, negatives = set(), set()
        for event in news_events[:30]:
            score, pos, neg = _terms_score(
                (event.get("title") or "") + " " + (event.get("summary") or "")
            )
            news_score += score
            positives.update(pos)
            negatives.update(neg)
        news_score = max(-10, min(10, news_score))
        recent_filings = []
        for event in sec_events[:20]:
            form = str((event.get("metadata") or {}).get("form", ""))
            recent_filings.append({"form": form, "title": event["title"],
                                   "filed_at": event.get("published_at"),
                                   "url": event.get("canonical_url")})
        # No fundamental ratios are fabricated. Lack of coverage is explicit.
        if news_score >= 3 and not negatives:
            status = "POSITIVE_NEWS_WATCH"
        elif news_score <= -3 or negatives:
            status = "RISK_REVIEW"
        else:
            status = "NEEDS_FUNDAMENTAL_RESEARCH"
        sentiment = _news_sentiment(news_events)
        card = {
            "symbol": symbol,
            "company": candidate.get("name", symbol),
            "market": {
                "price": candidate.get("price"),
                "daily_change_pct": candidate.get("change_pct"),
                "daily_dollar_volume": candidate.get("dollar_volume"),
                "feed": candidate.get("data_feed"),
            },
            "discovery_score": candidate.get("discovery_score"),
            "research_status": status,
            "news_score_heuristic": news_score,
            "positive_terms": sorted(positives),
            "risk_terms": sorted(negatives),
            "news_count_archived": len(news_events),
            "sec_filings": recent_filings,
            "technical": technical_by_symbol.get(symbol, {"status": "NOT_COLLECTED", "score": None}),
            "sentiment": sentiment,
            "fundamentals": fundamentals_by_symbol.get(symbol, {
                "status": "NOT_CONFIGURED",
                "note": "Set SEC_USER_AGENT to retrieve official SEC XBRL facts.",
                "metrics": {}, "ratios": {},
            }),
            "assessment": (
                "Deterministic screening using available annual SEC XBRL facts and "
                "keyword-based news signals. Not an LLM, price target, or trade instruction."
            ),
        }
        card["decision"] = classify_research(card)
        cards.append(card)
    return cards


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect news and build explainable stock research cards.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--db", default=os.environ.get("MARKET_EVENT_DB", "data/market_events.sqlite3"))
    args = parser.parse_args()
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        parser.error("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY locally.")
    store = MarketEventStore(args.db)
    discovery = AlpacaMarketDiscovery(key, secret)
    universe = discovery.run(limit=args.limit)
    candidates = universe["candidates"]
    rss_result = collect_feeds(store)
    sec_user_agent = os.environ.get("SEC_USER_AGENT")
    sec_filings_result = {"sources": [], "stored_total": 0, "status": "NOT_CONFIGURED"}
    if sec_user_agent:
        sec_filings_result = SECFilingsCollector(sec_user_agent).collect([item["symbol"] for item in candidates], store)
        sec_filings_result["status"] = "FETCHED"
    news_result = AlpacaNewsCollector(key, secret).collect(
        [item["symbol"] for item in candidates], store
    )
    fundamentals_by_symbol = {}
    fundamentals_status = "NOT_CONFIGURED"
    if sec_user_agent:
        fundamentals_by_symbol = SECCompanyFacts(sec_user_agent).collect([item["symbol"] for item in candidates])
        fundamentals_status = "FETCHED"
    technical_by_symbol = AlpacaTechnicalAnalyzer(key, secret).collect([item["symbol"] for item in candidates])
    cards = build_research_cards(candidates, store, args.limit, fundamentals_by_symbol, technical_by_symbol)
    shortlist = select_shortlist(cards, limit=5)
    shortlist_by_symbol = {item["symbol"]: item["investment_review"] for item in shortlist}
    for card in cards:
        card["shortlisted"] = card["symbol"] in shortlist_by_symbol
        if card["shortlisted"]:
            card["investment_review"] = shortlist_by_symbol[card["symbol"]]
    saved_cards = store.save_research_cards(cards)
    archived_events = store.list_events(limit=500)
    earnings_calendar_result = collect_earnings_calendar(store)
    alerts = generate_alerts(candidates, archived_events)
    saved_alerts = store.save_alerts(alerts)
    portfolio_impact_result = {"status": "UNAVAILABLE", "generated": 0, "saved": 0}
    try:
        portfolio_snapshot = build_snapshot(AlpacaReadOnlyClient(key, secret))
        impacts = analyze_portfolio_impact(portfolio_snapshot, archived_events)
        portfolio_impact_result = {
            "status": "AVAILABLE",
            "held_positions": sum(len(portfolio_snapshot.get("positions", {}).get(group, [])) for group in ("long", "short", "options", "other")),
            "generated": len(impacts),
            "saved": store.save_portfolio_impacts(impacts),
            "read_only": True,
        }
    except Exception as exc:
        portfolio_impact_result = {"status": "ERROR", "error": type(exc).__name__, "generated": 0, "saved": 0}
    print(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "discovery": {"assets_discovered": universe["assets_discovered"],
                      "candidate_count": universe["candidate_count"]},
        "rss_collection": rss_result,
        "news_collection": news_result,
        "sec_filings_collection": sec_filings_result,
        "research_cards_saved": saved_cards,
        "investment_shortlist": {"selected": len(shortlist), "max_selected": 5,
                                 "paper_buy_candidates": sum(1 for item in shortlist if item["investment_review"]["decision"] == "PAPER_BUY_CANDIDATE"),
                                 "symbols": [item["symbol"] for item in shortlist],
                                 "method": "conservative_rules_v1", "orders_submitted": 0},
        "earnings_calendar": earnings_calendar_result,
        "alerts_generated": len(alerts),
        "alerts_saved": saved_alerts,
        "portfolio_impact": portfolio_impact_result,
        "fundamentals_status": fundamentals_status,
        "technical_analysis": {"available": sum(1 for item in technical_by_symbol.values() if item.get("status") == "AVAILABLE"),
                               "total": len(technical_by_symbol), "method": "SMA20_SMA50_RSI14_v1"},
        "decision_counts": {label: sum(1 for card in cards if card["decision"]["decision"] == label) for label in ("CANDIDATE", "WATCH", "AVOID")},
        "read_only": True,
        "orders_submitted": 0,
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
