import unittest
from forward_performance import evaluate_snapshot


class ForwardPerformanceTests(unittest.TestCase):
    def test_horizons_use_bars_after_snapshot_and_entry(self):
        snapshot = {"symbol": "XYZ", "observed_at": "2025-01-01T15:00:00Z"}
        bars = [{"bar_at": f"2025-01-{day:02d}T21:00:00+00:00", "close": close}
                for day, close in [(1, 100), (2, 101), (3, 102), (4, 103), (5,104), (6,105),
                                   (7,106), (8,107), (9,108), (10,109), (11,110), (12,111),
                                   (13,112), (14,113), (15,114), (16,115), (17,116), (18,117),
                                   (19,118), (20,119)]]
        result = evaluate_snapshot(snapshot, bars)
        self.assertEqual(result["entry"]["close"], 100)
        self.assertEqual(result["horizons"]["j1"]["return_pct"], 1.0)
        self.assertEqual(result["horizons"]["j5"]["status"], "COMPLETE")
        self.assertEqual(result["horizons"]["j20"]["status"], "PENDING")

    def test_missing_future_bars_are_pending(self):
        result = evaluate_snapshot({"symbol":"ABC","observed_at":"2025-01-01T00:00:00Z"},
                                   [{"bar_at":"2025-01-02T00:00:00Z","close":10}])
        self.assertEqual(result["status"], "IN_PROGRESS")
        self.assertEqual(result["horizons"]["j1"]["status"], "PENDING")

    def test_invalid_timestamp_is_rejected(self):
        result = evaluate_snapshot({"symbol":"ABC","observed_at":"bad"}, [])
        self.assertEqual(result["status"], "INVALID_SNAPSHOT_TIME")


if __name__ == "__main__":
    unittest.main()
