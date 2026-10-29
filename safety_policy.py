"""Central safety policy for the portfolio analyst.

Trading is deliberately disabled. Change this only in a separately reviewed
future change after explicit user authorization and complete safety testing.
"""
TRADING_ENABLED = False


class TradingDisabledError(RuntimeError):
    """Raised whenever code attempts to submit or cancel a transaction."""


def require_trading_enabled(action: str = "transaction") -> None:
    if not TRADING_ENABLED:
        raise TradingDisabledError(
            f"Blocked {action}: this agent is configured for analysis and proposals only. "
            "No order was sent or cancelled."
        )
