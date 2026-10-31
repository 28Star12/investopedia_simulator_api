# SEC EDGAR filings collector

The SEC collector adds official public filing metadata to the same local event
archive used by the dashboard. It supports 8-K, 10-K, 10-Q, 20-F, 6-K, S-1,
S-3, and DEF 14A filings. It does not log in or submit anything to the SEC.

## Configure SEC identification

The SEC requires a descriptive User-Agent that identifies the application and
provides a valid contact. Set it locally; do not commit it or paste it into
chat. For example, use your own valid contact information:

```bash
export SEC_USER_AGENT="MarketMonitor contact: YOUR_VALID_EMAIL"
```

## Collect for symbols

```bash
python sec_filings_collector.py --symbols AAPL,MSFT
```

Or set `WATCHLIST_SYMBOLS=AAPL,MSFT` and omit `--symbols`. Limit results
with `--limit 10`. The collector resolves ticker-to-CIK mappings from the
SEC's public company_tickers.json file, then reads each company's recent
submissions JSON. It stores filing date, form, accession number, symbol, and
official SEC archive link.

Run the collector as a separate one-shot command, then refresh the dashboard.
The dashboard does not trigger external requests. SEC filing date is recorded
as a date-only UTC timestamp, not an assertion about the precise filing time.
