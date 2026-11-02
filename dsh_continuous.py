"""Asynchronous Router/Worker control plane shared by all external channels."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from ego_core import Ego
from ego_runtime import Runtime

ROOT = Path(__file__).resolve().parent
WORKERS = ROOT / "reports" / "workers"
OUTBOX_SCHEMA = """
CREATE TABLE IF NOT EXISTS router_notifications(
 work_id TEXT PRIMARY KEY,reply_to TEXT,state TEXT NOT NULL,
 response TEXT,created_at TEXT NOT NULL,sent_at TEXT);
"""


class ContinuousEngine:
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self.processes: dict[str, subprocess.Popen] = {}
        WORKERS.mkdir(parents=True, exist_ok=True)
        with Ego(ROOT) as core:
            existed = core.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='router_notifications'").fetchone()
            core.db.executescript(OUTBOX_SCHEMA)
            if not existed:
                core.db.execute("INSERT INTO router_notifications(work_id,reply_to,state,created_at) SELECT id,NULL,'sent',? FROM work_items WHERE state IN('succeeded','failed','cancelled')", (time.time(),))
                core.db.commit()

    def tick(self, deliver) -> None:
        with Ego(ROOT) as core:
            core.db.executescript(OUTBOX_SCHEMA)
            runtime = Runtime(core)
            self._reap(core.db)
            pending = self._pending(core.db)
            slow = []
            for trigger in pending:
                subscribed = core.db.execute(
                    "SELECT 1 FROM thread_subscriptions WHERE thread_id=?", (trigger["thread_id"],)).fetchone()
                if subscribed:
                    runtime.route(trigger["id"], "direct", "Fast Path：已有活动 Thread 订阅，直通全部相关 Worker")
                else:
                    slow.append(trigger)
            if slow:
                self._route_batch(slow)
            self._dispatch(core.db)
            self._notify(core.db, deliver)

    def _pending(self, db) -> list[dict]:
        rows = db.execute("SELECT * FROM triggers WHERE status='pending' ORDER BY created_at LIMIT 50").fetchall()
        result = []
        for row in rows:
            payload = json.loads(row["payload"])
            text = str(payload.get("text", ""))
            if len(text) > 500:
                payload["text"] = text[:500]
                payload["spilled_chars"] = len(text) - 500
            result.append({"trigger_id": row["id"], "thread_id": row["thread_id"],
                           "source": row["source"], "kind": row["kind"], "payload": payload})
        return result

    def _route_batch(self, batch: list[dict]) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", dir=ROOT / "reports", delete=False) as file:
            json.dump(batch, file, ensure_ascii=False)
            path = Path(file.name)
        try:
            result = subprocess.run([sys.executable, "dsh_ego_router.py", "--batch", str(path)],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=1900)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
        finally:
            path.unlink(missing_ok=True)

    def _dispatch(self, db) -> None:
        available = self.max_workers - len(self.processes)
        if available <= 0:
            return
        rows = db.execute("SELECT id FROM work_items WHERE state='queued' ORDER BY priority DESC,created_at LIMIT ?", (available,)).fetchall()
        for row in rows:
            work_id = row["id"]
            log = (WORKERS / f"{work_id}.log").open("a", encoding="utf-8")
            process = subprocess.Popen([sys.executable, "dsh_ego_worker.py", work_id], cwd=ROOT,
                stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
                start_new_session=os.name != "nt")
            self.processes[work_id] = process

    def _reap(self, db) -> None:
        for work_id, process in list(self.processes.items()):
            if process.poll() is None:
                continue
            state = db.execute("SELECT state FROM work_items WHERE id=?", (work_id,)).fetchone()["state"]
            startup_grace = state == "queued" and time.time() - (WORKERS / f"{work_id}.log").stat().st_mtime < 120
            if not startup_grace:
                del self.processes[work_id]

    def _notify(self, db, deliver) -> None:
        db.executescript(OUTBOX_SCHEMA)
        rows = db.execute("SELECT id,state FROM work_items WHERE state IN('succeeded','failed','waiting','cancelled')").fetchall()
        for row in rows:
            exists = db.execute("SELECT 1 FROM router_notifications WHERE work_id=?", (row["id"],)).fetchone()
            if exists:
                continue
            reply = db.execute("SELECT external_id FROM triggers WHERE thread_id=(SELECT thread_id FROM work_items WHERE id=?) AND external_id IS NOT NULL ORDER BY created_at DESC LIMIT 1", (row["id"],)).fetchone()
            db.execute("INSERT INTO router_notifications VALUES(?,?, 'pending',NULL,?,NULL)",
                       (row["id"], reply["external_id"] if reply else None, time.time()))
        db.commit()
        pending = db.execute("SELECT * FROM router_notifications WHERE state='pending' ORDER BY created_at").fetchall()
        for item in pending:
            result = subprocess.run([sys.executable, "dsh_ego_router.py", "--notify", item["work_id"]],
                                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=1900)
            if result.returncode:
                raise RuntimeError(result.stderr or result.stdout)
            response = json.loads(result.stdout)["text"]
            if item["reply_to"]:
                deliver(item["reply_to"], response, item["work_id"])
            db.execute("UPDATE router_notifications SET state='sent',response=?,sent_at=? WHERE work_id=?",
                       (response, time.time(), item["work_id"]))
            db.commit()
