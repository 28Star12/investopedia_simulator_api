"""Deterministic, read-only portfolio diagnostics.

These are descriptive risk indicators, not personalized financial advice or trade
instructions. The module performs no network calls and cannot place orders.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def analyze_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    account = snapshot.get("account", {})
    positions = snapshot.get("positions", {})
    account_value = _number(account.get("account_value"))
    cash = _number(account.get("cash"))

    all_positions: list[dict[str, Any]] = []
    for category in ("long", "short", "options"):
        for position in positions.get(category, []) or []:
            enriched = dict(position)
            enriched["category"] = category
            all_positions.append(enriched)

    total_position_value = Decimal("0")
    position_values: list[tuple[str, Decimal, str]] = []
    missing_values = 0
    for position in all_positions:
        value = _number(position.get("market_value"))
        symbol = str(
            position.get("underlying_symbol") or position.get("symbol") or "Unknown"
        )
        if value is None:
            missing_values += 1
            continue
        total_position_value += abs(value)
        position_values.append((symbol, abs(value), str(position["category"])))

    concentration = []
    if total_position_value > 0:
        by_symbol: dict[str, Decimal] = {}
        for symbol, value, _category in position_values:
            by_symbol[symbol] = by_symbol.get(symbol, Decimal("0")) + value
        concentration = [
            {
                "symbol": symbol,
                "absolute_market_value": str(value),
                "share_of_tracked_positions_pct": str(
                    (value / total_position_value * 100).quantize(Decimal("0.01"))
                ),
            }
            for symbol, value in sorted(
                by_symbol.items(), key=lambda item: item[1], reverse=True
            )
        ]

    flags: list[dict[str, str]] = []
    if positions.get("short"):
        flags.append({
            "level": "warning",
            "code": "SHORT_EXPOSURE",
            "message": "The portfolio contains short positions, which can create losses greater than the initial proceeds.",
        })
    if positions.get("options"):
        flags.append({
            "level": "warning",
            "code": "OPTIONS_EXPOSURE",
            "message": "The portfolio contains options; expiration, contract type, and underlying exposure should be reviewed.",
        })
    if missing_values:
        flags.append({
            "level": "info",
            "code": "INCOMPLETE_POSITION_VALUES",
            "message": f"{missing_values} position(s) lack a usable market value, so concentration calculations are incomplete.",
        })
    if len(all_positions) == 0:
        flags.append({
            "level": "info",
            "code": "NO_OPEN_POSITIONS",
            "message": "No open positions were present in the supplied snapshot.",
        })

    cash_pct = None
    if account_value is not None and account_value > 0 and cash is not None:
        cash_pct = str((cash / account_value * 100).quantize(Decimal("0.01")))

    return {
        "type": "descriptive_diagnostics",
        "not_financial_advice": True,
        "position_count": len(all_positions),
        "long_count": len(positions.get("long", []) or []),
        "short_count": len(positions.get("short", []) or []),
        "options_count": len(positions.get("options", []) or []),
        "cash_as_pct_of_account_value": cash_pct,
        "tracked_absolute_position_value": str(total_position_value),
        "largest_exposures": concentration[:5],
        "flags": flags,
        "limitations": [
            "This report uses only values present in the portfolio snapshot.",
            "It does not fetch news, current market prices, volatility, or fundamentals.",
            "It does not forecast returns or recommend specific trades.",
        ],
    }
