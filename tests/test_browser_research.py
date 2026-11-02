import unittest

from browser_research import BrowserResearchError, validate_research_url


class BrowserResearchURLTests(unittest.TestCase):
    def test_accepts_https_allowlisted_host(self):
        self.assertEqual(
            validate_research_url("https://www.nasdaq.com/market-activity"),
            "https://www.nasdaq.com/market-activity",
        )

    def test_accepts_subdomain(self):
        self.assertEqual(
            validate_research_url("https://www.sec.gov/edgar"),
            "https://www.sec.gov/edgar",
        )

    def test_rejects_http(self):
        with self.assertRaises(BrowserResearchError):
            validate_research_url("http://nasdaq.com")

    def test_rejects_unlisted_host_and_suffix_spoof(self):
        for url in (
            "https://example.com",
            "https://nasdaq.com.attacker.example",
        ):
            with self.subTest(url=url), self.assertRaises(BrowserResearchError):
                validate_research_url(url)

    def test_rejects_embedded_credentials(self):
        with self.assertRaises(BrowserResearchError):
            validate_research_url("https://user:pass@nasdaq.com")


if __name__ == "__main__":
    unittest.main()
