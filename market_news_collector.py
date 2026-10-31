"""One-shot collector for trusted public RSS/Atom feeds; no account access."""
from __future__ import annotations

import argparse
import email.utils
import os
import socket
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

from market_event_store import MarketEventStore


DEFAULT_FEEDS = (
    ("cnbc_top_news", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("yahoo_finance", "https://finance.yahoo.com/news/rssindex"),
)
ALLOWED_FEED_HOSTS = {"cnbc.com", "www.cnbc.com", "finance.yahoo.com"}
USER_AGENT = "ReadOnlyMarketResearch/1.0 (+public RSS reader)"


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, *names: str) -> str | None:
    wanted = set(names)
    for child in element.iter():
        if _local_name(child.tag) in wanted and child.text:
            value = child.text.strip()
            if value:
                return value
    return None


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(xml_text: str, source: str) -> list[dict]:
    if not isinstance(xml_text, str) or len(xml_text) > 2_000_000:
        raise ValueError("RSS response is empty or exceeds the 2 MB safety limit.")
    # ElementTree does not resolve external entities; reject DTD declarations too.
    if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
        raise ValueError("DTD/entity declarations are not accepted in RSS feeds.")
    root = ET.fromstring(xml_text)
    items = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    events = []
    for item in items[:100]:
        title = _child_text(item, "title")
        if not title:
            continue
        link = None
        for node in item.iter():
            if _local_name(node.tag) == "link":
                link = node.attrib.get("href") or (node.text or "").strip() or None
                if link:
                    break
        guid = _child_text(item, "guid", "id")
        summary = _child_text(item, "description", "summary", "content")
        published = _child_text(item, "pubdate", "published", "updated", "date")
        events.append({
            "source": source,
            "source_id": guid or link,
            "url": link,
            "title": title,
            "summary": summary,
            "published_at": _parse_date(published),
            "event_type": "news",
            "metadata": {"collector": "rss"},
        })
    return events


def validate_feed_url(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or host not in ALLOWED_FEED_HOSTS or parts.username or parts.password:
        raise ValueError("Feed URL must use HTTPS and an explicitly allowed publisher host.")
    return url


def collect_feeds(store: MarketEventStore, feeds=DEFAULT_FEEDS, timeout: int = 15) -> dict:
    results = []
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    for source, url in feeds:
        try:
            validate_feed_url(url)
            response = session.get(url, timeout=timeout, allow_redirects=False)
            if response.is_redirect or response.is_permanent_redirect:
                raise ValueError("RSS redirects are not followed; configure the final trusted HTTPS URL.")
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise ValueError("RSS response exceeds the 2 MB safety limit.")
            parsed = parse_feed(response.text, source)
            saved = store.add_events(parsed)
            results.append({"source": source, "fetched": len(parsed), "stored": len(saved), "error": None})
        except (requests.RequestException, ValueError, ET.ParseError, socket.timeout) as exc:
            results.append({"source": source, "fetched": 0, "stored": 0, "error": str(exc)[:300]})
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "sources": results,
        "stored_total": sum(item["stored"] for item in results),
        "read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect public financial RSS headlines into the local SQLite archive.")
    parser.add_argument("--db", default=os.environ.get("MARKET_EVENT_DB", "data/market_events.sqlite3"))
    args = parser.parse_args()
    result = collect_feeds(MarketEventStore(args.db))
    for item in result["sources"]:
        status = f"{item['stored']} saved" if not item["error"] else f"error: {item['error']}"
        print(f"{item['source']}: {status}")
    print(f"Total saved: {result['stored_total']} (read-only)")
    return 0 if all(item["error"] is None for item in result["sources"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
