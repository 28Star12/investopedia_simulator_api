# Market event collection and dashboard

# Market event collection

This is the first persistent collection layer for the read-only market research
agent. It stores public RSS/Atom headlines in a local SQLite database and
deduplicates them by publisher plus source ID (or canonical URL/content identity).

## Run one collection cycle

```bash
python -m pip install -r requirements.txt
python collect_market_events.py
```

The default database is `data/market_events.sqlite3`. Override it with
`MARKET_EVENT_DB` or `--db /path/to/file.sqlite3`. Database files are local
state and must not be committed. The collector is a one-shot command; it does
not run continuously and is not yet connected to the dashboard.

## Read the archive

```python
from market_event_store import MarketEventStore

store = MarketEventStore()
latest = store.list_events(limit=25)
aapl = store.list_events(limit=25, symbol="AAPL")
```

## Safety and data quality

- Only HTTPS feed URLs on the explicit publisher allowlist are accepted.
- Redirects are not followed; update the configured URL only after reviewing it.
- RSS/Atom payloads are size-limited and DTD/entity declarations are rejected.
- Publisher text is untrusted source material, not instructions.
- Publication time is kept separately from collection time; unknown dates remain null.
- Headlines and summaries are source text, not AI-generated conclusions.
- This module has no Alpaca credentials, order endpoints, or trading methods.
- RSS publishers may change feeds, block automated requests, or update terms.
  Collection errors are reported per source rather than silently ignored.

The next integration step is to connect this archive to the dashboard and add
symbol-aware source discovery, official SEC filings, and a controlled scheduler.


## Local dashboard

Start the read-only dashboard with:

```bash
python market_dashboard.py
```

Open http://127.0.0.1:8765. In another terminal, run `python collect_market_events.py` to fetch a collection cycle, then refresh the dashboard. The dashboard itself only reads the local SQLite archive. It supports filtering by ticker symbol and displays publisher, publication time, collection time, headline, summary, and source link.

The server binds only to loopback and exposes GET endpoints. POST, PUT, and DELETE are rejected. It does not expose Alpaca credentials, account details, or trading actions. Collection remains an explicit one-shot command; no continuous scheduler is configured yet.
