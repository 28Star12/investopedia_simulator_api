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


## Automatic stock discovery (no ticker list required)

Run the autonomous discovery pass:

```bash
python market_universe.py --limit 100
```

It retrieves the account's active, tradable US-equity asset universe from Alpaca,
then requests IEX market snapshots in batches. It screens for a minimum price
and daily dollar volume, and ranks candidates with a transparent discovery
score (liquidity is weighted more heavily than absolute daily movement).
No ticker symbols need to be supplied. The default thresholds are $5 minimum
price and $1,000,000 daily dollar volume; adjust with `--min-price` and
`--min-dollar-volume`.

This is a **discovery shortlist**, not an AI buy recommendation. IEX-only
snapshots can omit symbols and may not represent the consolidated market.
The next stages are fundamental/news/SEC analysis, persistent candidate
history, and dashboard integration. This command is GET-only and cannot place,
modify, or cancel orders. It uses the locally configured Alpaca Paper Trading
API credentials; never put them in source control or chat.


## Automatic dashboard alerts

Each research cycle stores deduplicated alerts for daily snapshot moves of at
least 3% (MEDIUM) or 5% (HIGH), archived news containing configured material
risk/positive keywords, and archived SEC filings. An 8-K is marked HIGH priority
for review; that does not imply the filing is negative.

Start the dashboard with `python market_dashboard.py`, then run
`python market_research.py --limit 100` to perform a discovery/news/fundamentals
cycle and generate alerts. Refresh the dashboard to view them. Price alerts are
deduplicated per symbol and UTC day; news and filing alerts are deduplicated by
their archived event identity. SEC alerts appear only after SEC filings have
been collected. These are rule-based prompts for human review, not verified
causal explanations or investment recommendations.

This is still a one-shot monitoring cycle: it does not run continuously or
send email/Discord/push notifications. All components remain read-only; no
orders can be placed, modified, or cancelled.


## Recency-aware sentiment analysis

The sentiment analyst uses archived Alpaca news headlines and summaries from the latest 14 days. Articles inside that window are weighted with exponential decay (3.5-day half-life), so newer reports influence the score more than older ones. Articles older than 14 days are excluded; undated items are also excluded rather than treated as current. If no dated recent articles remain, the score is null and the status is `NO_RECENT_NEWS` (or `NO_NEWS` when the archive is empty). This is a keyword-based news-tone proxy, not a measure of investor consensus. The technical, sentiment, and fundamental analysts retain equal one-third weights in the combined committee score.

## Earnings calendar (announcement-based)

Each research cycle scans the archived Alpaca/RSS news for explicit earnings-date
announcements. It stores one record per ticker and source article, preserving the
publisher, original headline, publication timestamp, and HTTPS source link.
A date is marked `DATE_CONFIRMED` only when the headline or summary contains a
full calendar date including the year. Announcements without a full date remain
`DATE_UNCONFIRMED`; the system does not infer dates from historical reporting
patterns or third-party estimates. Publisher-extracted dates should still be
verified against the company's investor-relations page.

The dashboard exposes these records under **Upcoming earnings calendar** and
through `GET /api/earnings`. Past confirmed dates are omitted from the upcoming
view; undated announcements remain visible. The collection is read-only and
does not submit, modify, or cancel orders.

This is not yet a comprehensive exchange earnings calendar: it can only find
announcements present in the collected news archive. A future historical
simulation must use point-in-time price bars and point-in-time news/filing
availability, plus snapshots of each decision as it was made. Recalculating
past decisions with today's news or fundamentals would introduce look-ahead
bias, so the simulation remains disabled until that history is available.
