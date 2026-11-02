# Automatic market monitoring

The dashboard can run the research pipeline automatically while its Python process remains alive.

## Start

Set the credentials in the Codespaces terminal (never commit them or paste them into chat):

\`\`\`bash
export APCA_API_KEY_ID="your-paper-key-id"
export APCA_API_SECRET_KEY="your-paper-secret-key"
export SEC_USER_AGENT="MarketMonitor contact: YOUR_VALID_EMAIL"
\`\`\`

Then start the dashboard:

\`\`\`bash
python market_dashboard.py
\`\`\`

With both Alpaca environment variables present, the first research cycle starts automatically. The default interval is 15 minutes. It discovers liquid US equities, collects public RSS headlines, Alpaca news, SEC filings and available SEC XBRL facts, then saves research cards and alerts in the same SQLite database used by the dashboard.

## Configure

Optional environment variables:

- \`MARKET_MONITOR_INTERVAL_SECONDS\`: cycle interval, clamped between 300 seconds and 86400 seconds (default 900).
- \`MARKET_MONITOR_LIMIT\`: maximum discovered stocks per cycle (default 100).
- \`MARKET_EVENT_DB\`: SQLite archive path (default \`data/market_events.sqlite3\`).
- \`MARKET_DASHBOARD_PORT\`: dashboard port (default 8765).

Use \`python market_dashboard.py --no-monitor\` to run only the dashboard without starting automatic cycles. The header displays the monitor state, last cycle, next cycle and any execution error. The status is also available at \`/api/monitor\`.

## Runtime limitation

The scheduler is a background thread owned by the dashboard process. It stops when the dashboard process stops and pauses when the Codespace is suspended or shut down. It is not an always-on hosted service. Keep the Codespace active while monitoring is needed; a persistent external scheduler/host would be a separate deployment step.

## Safety

All market-data and SEC collection is read-only. This pipeline only makes data retrieval requests, stores research and alerts, and submits zero orders. It never creates, modifies or cancels trades.
