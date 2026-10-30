import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from market_dashboard import create_server


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.server = create_server(port=0, db_path=str(Path(self.temp.name) / "events.sqlite3"))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%s" % self.server.server_address[1]
        self.server.RequestHandlerClass.store.add_event({
            "source": "unit-test", "source_id": "1", "title": "AAPL test headline",
            "summary": "A sample story", "url": "https://example.com/story",
            "published_at": "2026-10-29T12:00:00Z", "symbols": ["AAPL"],
        })

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_dashboard_home(self):
        with urlopen(self.base + "/") as response:
            body = response.read().decode()
            self.assertEqual(response.status, 200)
            self.assertIn("Market Monitor", body)
            self.assertIn("Filter symbol", body)

    def test_api_returns_events_and_read_only_flag(self):
        with urlopen(self.base + "/api/events") as response:
            payload = json.loads(response.read())
            self.assertTrue(payload["read_only"])
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["events"][0]["title"], "AAPL test headline")

    def test_symbol_filter_and_limit(self):
        with urlopen(self.base + "/api/events?symbol=MSFT&limit=9999") as response:
            payload = json.loads(response.read())
            self.assertEqual(payload["count"], 0)
        with urlopen(self.base + "/api/events?symbol=AAPL") as response:
            self.assertEqual(json.loads(response.read())["count"], 1)

    def test_unknown_path_and_write_methods_are_rejected(self):
        with self.assertRaises(HTTPError) as missing:
            urlopen(self.base + "/not-found")
        self.assertEqual(missing.exception.code, 404)
        request = Request(self.base + "/api/events", data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as rejected:
            urlopen(request)
        self.assertEqual(rejected.exception.code, 405)

    def test_non_loopback_binding_is_rejected(self):
        with self.assertRaises(ValueError):
            create_server(host="0.0.0.0", port=0, db_path=str(Path(self.temp.name) / "other.sqlite3"))


if __name__ == "__main__":
    unittest.main()
