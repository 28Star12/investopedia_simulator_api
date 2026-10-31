# SEC XBRL fundamentals and research decisions

The research pipeline can retrieve public company facts from SEC EDGAR and
calculate transparent screening labels. It is read-only: it never places,
changes, or cancels orders.

## Configure SEC identification once in the Codespace

The SEC requires a descriptive User-Agent with a valid contact. Set your own
contact locally (never paste it into chat or commit it):

```bash
export SEC_USER_AGENT="MarketMonitor contact: YOUR_VALID_EMAIL"
```

The pipeline also needs your existing Alpaca paper API credentials in the
environment. Then run:

```bash
python market_research.py --limit 100
```

Refresh the dashboard at port 8765. Research cards show CANDIDATE, WATCH, or
AVOID, with reasons, risks, missing data, and available annual SEC facts.

## How the labels work

- CANDIDATE: sufficient fundamental coverage and a strong score without a
  detected risk flag. This means research priority, not an instruction to buy.
- WATCH: mixed signals or insufficient SEC data.
- AVOID: material negative fundamentals or negative news signals under the
  current conservative rules.

The first version uses annual SEC XBRL facts (revenue, operating income, net
income, assets, liabilities, operating cash flow and selected other concepts).
Facts can have different fiscal period ends, accounting taxonomies, units, or
company reporting conventions. The card includes the source and period details;
missing values remain missing and are never guessed. This is not a complete
valuation model: it does not yet establish fair value, forecast growth, compare
industry peers, or model future earnings.

News scoring is still a simple keyword heuristic, not semantic AI. Treat all
labels as screening aids requiring human review. No automated trading actions
exist or are permitted in this project.
