"""Conservative earnings-date extraction from archived news; never estimates dates."""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any

_MONTHS = ("January February March April May June July August September October November December").split()
_MONTH_PATTERN = "|".join(_MONTHS)
_DATE_PATTERNS = (
    re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b"),
    re.compile(rf"\b({_MONTH_PATTERN})\s+([0-3]?\d)(?:st|nd|rd|th)?[,]?\s+(20\d{{2}})\b", re.I),
    re.compile(rf"\b([0-3]?\d)\s+({_MONTH_PATTERN})[,]?\s+(20\d{{2}})\b", re.I),
)
_EARNINGS_CUE = re.compile(
    r"\b(?:earnings|quarterly results|quarter results|financial results|results)\b",
    re.I,
)
_ANNOUNCEMENT_CUE = re.compile(
    r"\b(?:will report|to report|reports on|reporting on|announce(?:s)? on|"
    r"release(?:s)? (?:its )?(?:earnings|results) on|scheduled for|date set for)\b",
    re.I,
)


def extract_explicit_date(text: str) -> date | None:
    """Extract only a full year/month/day date; ambiguous dates are ignored."""
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text or "")
        if not match:
            continue
        try:
            if pattern is _DATE_PATTERNS[0]:
                year, month, day = map(int, match.groups())
            elif match.group(1).isalpha():
                month, day, year = match.groups()
                month = _MONTHS.index(month.title()) + 1
                day, year = int(day), int(year)
            else:
                day, month, year = match.groups()
                day, year = int(day), int(year)
                month = _MONTHS.index(month.title()) + 1
            return date(int(year), int(month), int(day))
        except (ValueError, TypeError):
            continue
    return None


def detect_earnings_announcements(events: list[dict[str, Any]], now: date | None = None) -> list[dict[str, Any]]:
    """Create one dated/undated calendar record per symbol and source article."""
    observed = now or datetime.now(timezone.utc).date()
    records = []
    for event in events:
        if event.get("event_type") != "news":
            continue
        text = " ".join((event.get("title") or "", event.get("summary") or ""))
        if not _EARNINGS_CUE.search(text) or not _ANNOUNCEMENT_CUE.search(text):
            continue
        announced_date = extract_explicit_date(text)
        source = str(event.get("source") or "unknown")
        source_id = str(event.get("source_id") or event.get("canonical_url") or event.get("id") or "")
        for symbol in sorted({str(value).strip().upper() for value in (event.get("symbols") or []) if str(value).strip()}):
            if not symbol:
                continue
            records.append({
                "source": "earnings_calendar",
                "source_id": f"{source}:{source_id}:{symbol}",
                "url": event.get("canonical_url"),
                "title": f"{symbol} earnings date announcement",
                "summary": event.get("title") or "",
                "published_at": event.get("published_at"),
                "symbols": [symbol],
                "event_type": "earnings_calendar",
                "metadata": {
                    "status": "DATE_CONFIRMED" if announced_date else "DATE_UNCONFIRMED",
                    "earnings_date": announced_date.isoformat() if announced_date else None,
                    "date_is_future": bool(announced_date and announced_date >= observed),
                    "original_source": source,
                    "original_source_id": source_id,
                    "original_title": event.get("title"),
                    "original_url": event.get("canonical_url"),
                    "extraction_method": "explicit_full_date_in_earnings_announcement_v1",
                    "date_source": "publisher headline/summary; verify against investor relations",
                },
            })
    return records


def collect_earnings_calendar(store, now: date | None = None) -> dict[str, Any]:
    """Scan archived news and persist only explicit announcements; no estimates."""
    archived = store.list_events(limit=500)
    records = detect_earnings_announcements(archived, now=now)
    saved = store.add_events(records)
    return {
        "scanned_news": sum(1 for item in archived if item.get("event_type") == "news"),
        "announcements_detected": len(records),
        "records_saved": len(saved),
        "confirmed_dates": sum(1 for item in records if item["metadata"]["status"] == "DATE_CONFIRMED"),
        "unconfirmed_dates": sum(1 for item in records if item["metadata"]["status"] == "DATE_UNCONFIRMED"),
        "read_only": True,
    }
