"""Read-only, headless browser research for public financial pages.

This collector only visits explicitly supplied HTTPS URLs on an allowlist. It
does not log in, click controls, submit forms, download files, or interact with
brokerage accounts. Page text is untrusted input and must never be treated as
instructions by an AI model.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DEFAULT_ALLOWED_DOMAINS = (
    "reuters.com",
    "cnbc.com",
    "finance.yahoo.com",
    "nasdaq.com",
    "sec.gov",
)
MAX_TEXT_CHARS = 20_000
NAVIGATION_TIMEOUT_MS = 20_000


class BrowserResearchError(ValueError):
    """Raised when a requested research URL is unsafe or invalid."""


def validate_research_url(url: str, allowed_domains=DEFAULT_ALLOWED_DOMAINS) -> str:
    """Accept HTTPS URLs only on an explicit domain allowlist."""
    if not isinstance(url, str) or not url.strip():
        raise BrowserResearchError("A non-empty URL is required.")
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise BrowserResearchError("Only credential-free HTTPS URLs are allowed.")
    allowed = tuple(domain.lower().lstrip(".") for domain in allowed_domains)
    if not any(host == domain or host.endswith("." + domain) for domain in allowed):
        raise BrowserResearchError("URL host is not on the research allowlist.")
    return url.strip()


def collect_public_pages(
    urls: list[str],
    *,
    allowed_domains=DEFAULT_ALLOWED_DOMAINS,
    max_pages: int = 8,
    timeout_ms: int = NAVIGATION_TIMEOUT_MS,
) -> list[dict[str, Any]]:
    """Collect visible text from public pages using an invisible Chromium browser."""
    if not isinstance(urls, list):
        raise BrowserResearchError("urls must be a list.")
    if max_pages < 1:
        raise BrowserResearchError("max_pages must be positive.")
    selected = [validate_research_url(url, allowed_domains) for url in urls[:max_pages]]
    results: list[dict[str, Any]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                java_script_enabled=True,
                accept_downloads=False,
                service_workers="block",
            )
            page = context.new_page()
            page.set_default_navigation_timeout(timeout_ms)
            for requested_url in selected:
                record: dict[str, Any] = {
                    "requested_url": requested_url,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "status": None,
                    "title": None,
                    "text": "",
                    "error": None,
                }
                try:
                    response = page.goto(requested_url, wait_until="domcontentloaded")
                    final_url = page.url
                    validate_research_url(final_url, allowed_domains)
                    record["url"] = final_url
                    record["status"] = response.status if response else None
                    record["title"] = page.title()[:300]
                    record["text"] = page.locator("body").inner_text(timeout=timeout_ms)[:MAX_TEXT_CHARS]
                except (PlaywrightTimeoutError, BrowserResearchError) as exc:
                    record["error"] = str(exc)[:300]
                except Exception as exc:
                    record["error"] = f"Page retrieval failed ({type(exc).__name__})."
                results.append(record)
            context.close()
        finally:
            browser.close()
    return results
