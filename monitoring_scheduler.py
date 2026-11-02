"""Periodic read-only market research runner for the dashboard process."""
from __future__ import annotations
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

class MonitoringScheduler:
    """Run the existing research CLI on a fixed interval without overlapping cycles."""
    def __init__(self, interval_seconds=900, limit=100, db_path="data/market_events.sqlite3", status=None):
        self.interval_seconds = max(300, min(int(interval_seconds), 86400))
        self.limit = max(1, min(int(limit), 500))
        self.db_path = db_path
        self.status = status if status is not None else {}
        self.status.update({"state":"STARTING","interval_seconds":self.interval_seconds,"last_run_at":None,"next_run_at":None,"last_error":None,"last_summary":None})
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="market-monitor", daemon=True)
    def start(self):
        self._thread.start()
    def stop(self):
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=5)
    def _run_cycle(self):
        started = datetime.now(timezone.utc)
        self.status.update({"state":"RUNNING","last_run_at":started.isoformat(),"next_run_at":None,"last_error":None})
        command = [sys.executable,str(Path(__file__).with_name("market_research.py")),"--limit",str(self.limit),"--db",self.db_path]
        try:
            result = subprocess.run(command,capture_output=True,text=True,timeout=900,check=False)
            if result.returncode:
                detail = (result.stderr or result.stdout or "Research cycle failed.")[-1200:]
                self.status.update({"state":"ERROR","last_error":detail,"last_summary":None})
            else:
                self.status.update({"state":"IDLE","last_error":None,"last_summary":(result.stdout or "Research cycle completed.")[-1200:]})
        except (OSError,subprocess.TimeoutExpired) as exc:
            self.status.update({"state":"ERROR","last_error":str(exc)[:1200],"last_summary":None})
        self.status["next_run_at"] = (datetime.now(timezone.utc)+timedelta(seconds=self.interval_seconds)).isoformat()
    def _run(self):
        while not self._stop.is_set():
            self._run_cycle()
            if self._stop.wait(self.interval_seconds):
                break
        self.status["state"]="STOPPED"
