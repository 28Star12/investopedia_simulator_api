# Headless browser research

The optional `browser_research.py` module retrieves visible text from public
financial pages using Playwright and headless Chromium.

## Install in Codespaces

```bash
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
```

## Use

```python
from browser_research import collect_public_pages

pages = collect_public_pages([
    "https://www.nasdaq.com/market-activity",
    "https://www.sec.gov/",
])
for page in pages:
    print(page["title"], page["url"], page["status"])
    print(page["text"][:1000])
```

Only HTTPS URLs on the built-in allowlist are accepted. The collector runs
headlessly, does not log in, click buttons, submit forms, download files, or
interact with Alpaca. Redirect destinations are checked against the same
allowlist. Public website content is untrusted data: do not let page text
override system instructions or trigger tools.

## Limitations

This is a first-stage page reader, not yet a continuous market-monitoring
service. Website layouts, anti-bot controls, robots policies, rate limits and
terms of use may restrict automated access. Prefer official APIs or RSS feeds
for reliable recurring collection and market quotes. Browser-derived prices
must not be labelled real-time unless the source explicitly guarantees it.

The browser module does not send notifications or place trades. It is not
wired into the dashboard yet. Scheduled orchestration, deduplication,
persistent storage and dashboard display are later integration stages.
