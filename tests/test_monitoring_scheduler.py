import unittest
from unittest.mock import patch
from monitoring_scheduler import MonitoringScheduler

class MonitoringSchedulerTests(unittest.TestCase):
    def test_interval_is_clamped(self):
        self.assertEqual(MonitoringScheduler(interval_seconds=10).interval_seconds,300)
    def test_success_updates_status(self):
        scheduler=MonitoringScheduler(interval_seconds=600,status={})
        with patch("monitoring_scheduler.subprocess.run") as run:
            run.return_value.returncode=0
            scheduler._run_cycle()
        self.assertEqual(scheduler.status["state"],"IDLE")
        self.assertIsNotNone(scheduler.status["last_run_at"])
        self.assertIsNotNone(scheduler.status["next_run_at"])
        self.assertIsNone(scheduler.status["last_error"])
    def test_failure_is_reported(self):
        scheduler=MonitoringScheduler(status={})
        with patch("monitoring_scheduler.subprocess.run") as run:
            run.return_value.returncode=1
            run.return_value.stderr="provider unavailable"
            run.return_value.stdout=""
            scheduler._run_cycle()
        self.assertEqual(scheduler.status["state"],"ERROR")
        self.assertIn("provider unavailable",scheduler.status["last_error"])

if __name__=="__main__":
    unittest.main()
