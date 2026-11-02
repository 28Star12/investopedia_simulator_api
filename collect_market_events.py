"""Backward-compatible entry point for public RSS collection."""
from market_news_collector import main


if __name__ == "__main__":
    raise SystemExit(main())
