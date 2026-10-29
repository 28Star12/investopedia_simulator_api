"""Deterministic, read-only portfolio diagnostics.

These are descriptive risk indicators, not personalized financial advice or trade
instructions. The module performs no network calls and cannot place orders.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

CONCENTRATION_NOTICE_PCT = Decimal("25")
CONCENTRATION_HIGH_PCT = Decimal("50")


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def _decimal_string(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _portfolio_performance(history: dict[str, Any], history_incomplete: bool) -> dict[str, Any]:
    """Calculate a simple history-period change, or explain why it is unavailable."""
    raw_equity = history.get("equity", []) or []
    usable = [value for value in (_number(item) for item in raw_equity) if value is not None]
    result: dict[str, Any] = {
        "available": False,
        "data_points": len(usable),
        "period": history.get("timeframe"),
        "starting_value": None,
        "ending_value": None,
        "absolute_change": None,
        "return_pct": None,
        "baseline": None,
        "limitation": None,
    }
    if history_incomplete:
        result["limitation"] = (
            "History appears incomplete or initializing; performance was not calculated."
        )
        return result
    if len(usable) < 2:
        result["limitation"] = "At least two valid equity observations are required."
        return result

    ending = usable[-1]
    base_value = _number(history.get("base_value"))
    if base_value is not None and base_value > 0:
        starting = base_value
        baseline = "base_value"
    else:
        starting = usable[0]
        baseline = "first_equity_observation"
    if starting <= 0:
        result["limitation"] = "A positive starting value is required to calculate return."
        return result

    change = ending - starting
    result.update({
        "available": True,
        "starting_value": _decimal_string(starting),
        "ending_value": _decimal_string(ending),
        "absolute_change": _decimal_string(change),
        "return_pct": _decimal_string(change / starting * 100),
        "baseline": baseline,
    })
    return result


def analyze_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    account = snapshot.get("account", {})
    positions = snapshot.get("positions", {})
    account_value = _number(account.get("account_value"))
    cash = _number(account.get("cash"))

    all_positions: list[dict[str, Any]] = []
    for category in ("long", "short", "options", "other"):
        for position in positions.get(category, []) or []:
            enriched = dict(position)
            enriched["category"] = category
            all_positions.append(enriched)

    total_position_value = Decimal("0")
    long_gross = Decimal("0")
    short_gross = Decimal("0")
    options_gross = Decimal("0")
    other_gross = Decimal("0")
    position_values: list[tuple[str, Decimal, str]] = []
    unrealized_by_category = {
        category: Decimal("0") for category in ("long", "short", "options", "other")
    }
    unrealized_positions = 0
    missing_unrealized_positions = 0
    missing_values = 0
    for position in all_positions:
        value = _number(position.get("market_value"))
        symbol = str(
            position.get("underlying_symbol") or position.get("symbol") or "Unknown"
        )
        unrealized_pl = _number(position.get("unrealized_pl"))
        if unrealized_pl is None:
            missing_unrealized_positions += 1
        else:
            unrealized_by_category[position["category"]] += unrealized_pl
            unrealized_positions += 1
        if value is None:
            missing_values += 1
            continue
        absolute_value = abs(value)
        total_position_value += absolute_value
        if position["category"] == "long":
            long_gross += absolute_value
        elif position["category"] == "short":
            short_gross += absolute_value
        elif position["category"] == "options":
            options_gross += absolute_value
        else:
            other_gross += absolute_value
        position_values.append((symbol, absolute_value, str(position["category"])))

    concentration = []
    if total_position_value > 0:
        by_symbol: dict[str, Decimal] = {}
        for symbol, value, _category in position_values:
            by_symbol[symbol] = by_symbol.get(symbol, Decimal("0")) + value
        concentration = [
            {
                "symbol": symbol,
                "absolute_market_value": _decimal_string(value),
                "share_of_tracked_positions_pct": _decimal_string(
                    value / total_position_value * 100
                ),
            }
            for symbol, value in sorted(
                by_symbol.items(), key=lambda item: item[1], reverse=True
            )
        ]

    stock_gross = long_gross + short_gross
    net_stock_exposure = long_gross - short_gross
    gross_exposure_pct = None
    if account_value is not None and account_value > 0:
        gross_exposure_pct = _decimal_string(
            (total_position_value / account_value) * 100
        )

    # Treat suspicious account-history data as a data-quality issue, not a loss.
    history = snapshot.get("portfolio_history", {}) or {}
    raw_equity = history.get("equity", []) or []
    usable_equity = [
        value for value in (_number(item) for item in raw_equity) if value is not None
    ]
    history_may_be_incomplete = False
    if len(usable_equity) >= 3 and usable_equity[-1] > 0:
        prior_equity = usable_equity[:-1]
        non_positive_prior = sum(value <= 0 for value in prior_equity)
        history_may_be_incomplete = (
            len(prior_equity) >= 2
            and non_positive_prior / len(prior_equity) >= Decimal("0.5")
        )

    flags: list[dict[str, str]] = []
    if history_may_be_incomplete:
        flags.append({
            "level": "info",
            "code": "HISTORY_MAY_BE_INCOMPLETE",
            "message": (
                "Portfolio history contains repeated zero or negative equity values "
                "before a positive latest value. The history may be incomplete or "
                "initializing; do not interpret it as a confirmed drawdown without "
                "checking the source data."
            ),
        })

    high_concentration = [
        item for item in concentration
        if _number(item["share_of_tracked_positions_pct"]) >= CONCENTRATION_HIGH_PCT
    ]
    elevated_concentration = [
        item for item in concentration
        if CONCENTRATION_NOTICE_PCT
        <= _number(item["share_of_tracked_positions_pct"])
        < CONCENTRATION_HIGH_PCT
    ]
    if high_concentration:
        symbols = ", ".join(item["symbol"] for item in high_concentration)
        flags.append({
            "level": "warning",
            "code": "HIGH_POSITION_CONCENTRATION",
            "message": (
                f"{symbols} each represent at least 50% of tracked position value. "
                "This is a concentration indicator, not a trade instruction."
            ),
        })
    elif elevated_concentration:
        symbols = ", ".join(item["symbol"] for item in elevated_concentration)
        flags.append({
            "level": "info",
            "code": "ELEVATED_POSITION_CONCENTRATION",
            "message": (
                f"{symbols} each represent at least 25% of tracked position value."
            ),
        })

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
    if missing_unrealized_positions:
        flags.append({
            "level": "info",
            "code": "INCOMPLETE_UNREALIZED_PNL",
            "message": (
                f"{missing_unrealized_positions} position(s) lack a usable unrealized "
                "profit/loss value, so the open-position P/L total is incomplete."
            ),
        })
    if missing_values:
        flags.append({
            "level": "info",
            "code": "INCOMPLETE_POSITION_VALUES",
            "message": f"{missing_values} position(s) lack a usable market value, so exposure and concentration calculations are incomplete.",
        })
    if len(all_positions) == 0:
        flags.append({
            "level": "info",
            "code": "NO_OPEN_POSITIONS",
            "message": "No open positions were present in the supplied snapshot.",
        })

    cash_pct = None
    if account_value is not None and account_value > 0 and cash is not None:
        cash_pct = _decimal_string(cash / account_value * 100)

    stock_gross_pct = None
    long_pct_of_stock_gross = None
    short_pct_of_stock_gross = None
    net_pct_of_account = None
    if account_value is not None and account_value > 0:
        net_pct_of_account = _decimal_string(net_stock_exposure / account_value * 100)
    if stock_gross > 0:
        long_pct_of_stock_gross = _decimal_string(long_gross / stock_gross * 100)
        short_pct_of_stock_gross = _decimal_string(short_gross / stock_gross * 100)
    if account_value is not None and account_value > 0:
        stock_gross_pct = _decimal_string(stock_gross / account_value * 100)

    return {
        "type": "descriptive_diagnostics",
        "not_financial_advice": True,
        "position_count": len(all_positions),
        "long_count": len(positions.get("long", []) or []),
        "short_count": len(positions.get("short", []) or []),
        "options_count": len(positions.get("options", []) or []),
        "other_count": len(positions.get("other", []) or []),
        "cash_as_pct_of_account_value": cash_pct,
        "tracked_absolute_position_value": _decimal_string(total_position_value),
        "largest_exposures": concentration[:5],
        "exposure_summary": {
            "long_gross_market_value": _decimal_string(long_gross),
            "short_gross_market_value": _decimal_string(short_gross),
            "options_gross_market_value": _decimal_string(options_gross),
            "other_gross_market_value": _decimal_string(other_gross),
            "stock_gross_market_value": _decimal_string(stock_gross),
            "stock_net_exposure": _decimal_string(net_stock_exposure),
            "stock_gross_as_pct_of_account_value": stock_gross_pct,
            "net_stock_exposure_as_pct_of_account_value": net_pct_of_account,
            "long_share_of_stock_gross_pct": long_pct_of_stock_gross,
            "short_share_of_stock_gross_pct": short_pct_of_stock_gross,
            "total_gross_positions_as_pct_of_account_value": gross_exposure_pct,
            "note": (
                "Gross values use absolute market values. Net stock exposure is long "
                "gross minus short gross; options are reported separately."
            ),
        },
        "open_positions_unrealized_pl": {
            "available": unrealized_positions > 0,
            "total": _decimal_string(sum(unrealized_by_category.values(), Decimal("0")))
            if unrealized_positions else None,
            "by_category": {
                category: _decimal_string(value) for category, value in unrealized_by_category.items()
            },
            "positions_with_data": unrealized_positions,
            "positions_missing_data": missing_unrealized_positions,
            "note": (
                "Sum of reported unrealized_pl values for currently open positions; "
                "not a realized return or a complete account performance measure."
            ),
        },
        "portfolio_performance": _portfolio_performance(history, history_may_be_incomplete),
        "flags": flags,
        "limitations": [
            "This report uses only values present in the portfolio snapshot.",
            "Exposure calculations use reported market values and may be incomplete when values are missing.",
            "History-period performance is not necessarily a calendar-year or lifetime return.",
            "It does not fetch news, current market prices, volatility, or fundamentals.",
            "It does not forecast returns or recommend specific trades.",
        ],
    }
