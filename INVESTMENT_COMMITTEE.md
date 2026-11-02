# Five-stock investment research committee

Each research cycle already discovers a broad universe of active, tradable US equities, collects market snapshots, public news and SEC filings, and retrieves annual SEC XBRL fundamentals when `SEC_USER_AGENT` is configured.

The committee now:
1. Reviews the researched universe and selects up to five companies with at least three of four core annual metrics available (revenue, operating income, net income and operating cash flow).
2. Scores positive financial performance, operating and net margins, liabilities/assets, archived news signals and daily dollar liquidity.
3. Checks whether SEC filing data is recent (no older than 550 days).
4. Blocks a paper-buy candidate when core data is incomplete, data is stale, material negative news keywords exist, or operating income, net income or operating cash flow is not positive.
5. Saves the shortlist and full reasons/risks in the existing SQLite research-card archive for the dashboard.

## Decision labels

- `PAPER_BUY_CANDIDATE`: passed the conservative screening gates. This is a candidate for a human-reviewed paper-trading exercise only.
- `DO_NOT_BUY`: did not pass every required gate. This is not a sell instruction.

The shortlist may contain fewer than five stocks if the available SEC data does not support five reviews. It must never fill the list with fabricated or missing fundamentals.

## Important distinction

The current committee is a deterministic, explainable screening engine (`conservative_rules_v1`), not a generative AI model. It does not claim to understand full filings or forecast future prices. The Gemini and Mistral clients in this repository are separate portfolio-question prototypes and are not invoked by this committee. A real LLM-based second opinion would require an available, age-eligible provider account and separate validation.

## Safety

- Research and recommendation only.
- No order endpoint is called.
- No order is submitted, modified or cancelled.
- The Alpaca client remains GET-only and pinned to Paper Trading account reads.
- No sell logic is included in this phase.
