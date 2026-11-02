"""Persistent asynchronous OS jobs for the non-blocking ReAct loop."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

from ego_core import EgoError, dumps, new_id, now

SCHEMA = """CREATE TABLE IF NOT EXISTS async_jobs(
 id TEXT PRIMARY KEY,work_id TEXT,command TEXT NOT NULL,cwd TEXT NOT NULL,pid INTEGER,
 state TEXT NOT NULL,output_path TEXT NOT NULL,exit_code INTEGER,created_at TEXT NOT NULL,finished_at TEXT);
"""


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            code = ctypes.c_ulong()
            active = bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
            ctypes.windll.kernel32.CloseHandle(handle)
            return active
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class AsyncJobs:
    def __init__(self, core):
        self.c = core; self.db = core.db
        self.db.executescript(SCHEMA); self.db.commit()
        self.root = Path(core.root).resolve()
        (self.root / "reports" / "async").mkdir(parents=True, exist_ok=True)

    def start(self, command: list[str], work_id: str | None = None, cwd: str | None = None):
        if not command or any(not isinstance(x, str) or not x for x in command):
            raise EgoError("command must be a non-empty string array")
        job = new_id("JOB"); at = now()
        output = self.root / "reports" / "async" / f"{job}.log"
        directory = str((self.root / (cwd or ".")).resolve())
        spec = Path(str(output) + ".command.json")
        spec.write_text(dumps(command), encoding="utf-8")
        output.touch()
        wrapper = [sys.executable, str(Path(__file__).with_name("ego_async_process.py")),
                   str(output) + ".exit", directory, "@" + str(spec)]
        if os.name == "nt":
            env = os.environ.copy()
            env["EGO_ASYNC_CMD"] = subprocess.list2cmdline(wrapper)
            env["EGO_ASYNC_CWD"] = directory
            script = ("$c=Invoke-CimMethod -ClassName Win32_Process -MethodName Create "
                      "-Arguments @{CommandLine=$env:EGO_ASYNC_CMD;CurrentDirectory=$env:EGO_ASYNC_CWD};"
                      "if($c.ReturnValue -ne 0){throw \"Win32_Process.Create failed: $($c.ReturnValue)\"};"
                      "Write-Output $c.ProcessId")
            launched = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script],
                cwd=directory, env=env, capture_output=True, text=True, timeout=20, check=True)
            pid = int(launched.stdout.strip().splitlines()[-1])
        else:
            process = subprocess.Popen(wrapper, cwd=directory, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
            pid = process.pid
        with self.db:
            self.db.execute("INSERT INTO async_jobs VALUES(?,?,?,?,?,'running',?,NULL,?,NULL)",
                (job, work_id, dumps(command), directory, pid, str(output), at))
            self.c.audit("async_job_started", [job] + ([work_id] if work_id else []), result=f"wmi_pid:{pid}")
        return {"job_id": job, "pid": pid, "state": "running", "output_path": str(output)}

    def _event(self, job, state):
        if not job["work_id"]:
            return
        from ego_runtime import Runtime
        work = self.db.execute("SELECT thread_id FROM work_items WHERE id=?", (job["work_id"],)).fetchone()
        if not work:
            return
        runtime = Runtime(self.c)
        trigger = runtime.ingest("async", state, work["thread_id"],
            {"text": f"后台任务 {job['id']} 已{state}，job_id={job['id']}，可用 ego_async_cli.py output 读取结果。", "job_id": job["id"]}, job["id"])
        runtime.route(trigger, "direct", "异步工具结果直通原 Worker")

    def poll(self, job_id: str):
        job = self.db.execute("SELECT * FROM async_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise EgoError("async job not found")
        exit_path = Path(job["output_path"] + ".exit")
        pid_path = Path(str(exit_path) + ".pid")
        if job["pid"] is None and pid_path.exists():
            self.db.execute("UPDATE async_jobs SET pid=? WHERE id=?", (int(pid_path.read_text()), job_id))
            self.db.commit()
            job = self.db.execute("SELECT * FROM async_jobs WHERE id=?", (job_id,)).fetchone()
        if job["state"] == "running" and exit_path.exists():
            exit_code = int(exit_path.read_text(encoding="utf-8"))
            state = "succeeded" if exit_code == 0 else "failed"
            with self.db:
                self.db.execute("UPDATE async_jobs SET state=?,exit_code=?,finished_at=? WHERE id=?", (state, exit_code, now(), job_id))
                self.c.audit("async_job_finished", [job_id], result=f"{state}:{exit_code}")
            self._event(job, state)
            job = self.db.execute("SELECT * FROM async_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(job)

    def output(self, job_id: str, limit: int = 4000):
        job = self.poll(job_id)
        text = Path(job["output_path"]).read_text(encoding="utf-8", errors="replace")
        return {"job_id": job_id, "state": job["state"], "exit_code": job["exit_code"], "output": text[-limit:],
                "spilled_chars": max(0, len(text) - limit), "output_path": job["output_path"]}

    def stop(self, job_id: str, reason: str):
        if not reason.strip():
            raise EgoError("stop reason required")
        job = self.db.execute("SELECT * FROM async_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise EgoError("async job not found")
        if job["state"] == "running" and alive(job["pid"]):
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(job["pid"]), "/T", "/F"], capture_output=True, check=False)
            else:
                os.killpg(job["pid"], 15)
        with self.db:
            self.db.execute("UPDATE async_jobs SET state='cancelled',finished_at=? WHERE id=?", (now(), job_id))
            self.c.audit("async_job_stopped", [job_id], result=reason)
        self._event(job, "cancelled")
        return {"job_id": job_id, "state": "cancelled"}
