"""Prospective signal outcome tracking from timestamped research and later daily bars."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


HORIZONS = (1, 5, 20)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def evaluate_snapshot(snapshot: dict[str, Any], bars: list[dict[str, Any]]) -> dict[str, Any]:
    """Use first close strictly after observation as entry; horizons count subsequent bars."""
    observed = _parse_time(snapshot.get("observed_at") or snapshot.get("generated_at"))
    valid = []
    for bar in bars:
        when = _parse_time(bar.get("bar_at") or bar.get("t"))
        try:
            close = float(bar.get("close", bar.get("c")))
        except (TypeError, ValueError):
            continue
        if when and close > 0:
            valid.append((when, close))
    valid.sort(key=lambda item: item[0])
    result = {"symbol": str(snapshot.get("symbol", "")).upper(),
              "snapshot_at": observed.isoformat() if observed else None,
              "entry": None, "horizons": {}, "method": "first_close_after_snapshot_v1",
              "disclaimer": "Prospective outcome monitoring only; not a backtest or trading instruction."}
    if observed is None:
        result["status"] = "INVALID_SNAPSHOT_TIME"
        return result
    later = [(when, close) for when, close in valid if when > observed]
    if not later:
        result["status"] = "WAITING_FOR_ENTRY_BAR"
        return result
    entry_time, entry_price = later[0]
    result["entry"] = {"bar_at": entry_time.isoformat(), "close": entry_price}
    for horizon in HORIZONS:
        target_index = later.index((entry_time, entry_price)) + horizon
        if target_index < len(later):
            target_time, target_price = later[target_index]
            result["horizons"][f"j{horizon}"] = {
                "status": "COMPLETE", "bar_at": target_time.isoformat(),
                "close": target_price, "return_pct": round((target_price / entry_price - 1) * 100, 4)}
        else:
            result["horizons"][f"j{horizon}"] = {"status": "PENDING", "bars_needed": target_index + 1 - len(later)}
    result["status"] = "COMPLETE" if all(x["status"] == "COMPLETE" for x in result["horizons"].values()) else "IN_PROGRESS"
    return result


def evaluate_history(store: Any, symbol: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
    snapshots = store.list_research_history(symbol=symbol, limit=limit)
    output = []
    cache: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        ticker = str(snapshot.get("symbol", "")).upper()
        if ticker not in cache:
            cache[ticker] = store.list_price_bars(ticker, limit=5000)
        outcome = evaluate_snapshot(snapshot, cache[ticker])
        outcome["snapshot_id"] = snapshot.get("id")
        decision = snapshot.get("investment_review") or {}
        outcome["decision"] = decision.get("decision")
        outcome["combined_score"] = decision.get("combined_score")
        output.append(outcome)
    return output
