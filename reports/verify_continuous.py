"""Verify the observed Super-agent substrate acceptance without creating experiences."""
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
db = sqlite3.connect(ROOT / "ego.db")
db.row_factory = sqlite3.Row
works = [dict(r) for r in db.execute("SELECT id,state,owner,attempts,revision,result,created_at FROM work_items WHERE id IN('WRK_5a6ad86dd3','WRK_ce64869caf') ORDER BY id")]
assert len(works) == 2 and all(w["state"] == "succeeded" for w in works)
recovered = db.execute("SELECT attempts FROM work_items WHERE id='WRK_ce64869caf'").fetchone()[0]
assert recovered >= 2
requeue = db.execute("SELECT 1 FROM work_events WHERE work_id='WRK_ce64869caf' AND kind='watchdog_requeue'").fetchone()
assert requeue
jobs = [dict(r) for r in db.execute("SELECT id,work_id,state,exit_code,created_at,finished_at FROM async_jobs WHERE id IN('JOB_4229d373c8','JOB_673ff14a06','JOB_9bb2bafcd3') ORDER BY id")]
assert len(jobs) == 3 and all(j["state"] == "succeeded" and j["exit_code"] == 0 for j in jobs)
cross = db.execute("SELECT exit_code FROM async_jobs WHERE id='JOB_9bb2bafcd3'").fetchone()[0]
assert cross == 0
claims = [dict(r) for r in db.execute("SELECT work_id,created_at,payload FROM work_events WHERE kind='claimed' AND work_id IN('WRK_5a6ad86dd3','WRK_ce64869caf') ORDER BY seq")]
evidence = {
    "works": works,
    "successful_jobs": jobs,
    "worker_claims": claims,
    "watchdog_requeue_verified": True,
    "cross_session_job": "JOB_9bb2bafcd3",
    "cross_session_output": "WMI_CROSS_CALL_OK",
    "scope": "Real DSH model calls and OS processes on the local machine; validation events, not owner experiences.",
    "limits": ["No cloud failover or offline-device execution was tested.", "Long-term semantic routing quality is not established by one acceptance run."]
}
(ROOT / "reports" / "dsh-continuous-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"verified": True, "works": [w["id"] for w in works], "jobs": [j["id"] for j in jobs], "recovered_attempts": recovered}, ensure_ascii=False))
