"""Start, inspect, or stop EGO-A's continuous service exactly once."""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
PID_FILE = REPORTS / "dsh-service.json"
CONSOLE = REPORTS / "dsh-service-console.log"


def saved_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    return json.loads(PID_FILE.read_text(encoding="utf-8")).get("pid")


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        active = bool(ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        ctypes.windll.kernel32.CloseHandle(handle)
        return active
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start() -> int:
    pid = saved_pid()
    if alive(pid):
        print(json.dumps({"status": "already_running", "pid": pid}))
        return 0
    REPORTS.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    legacy_node = Path.home() / ".openclaw" / "node"
    if legacy_node.exists():
        env["PATH"] = str(legacy_node) + os.pathsep + env.get("PATH", "")
    executable = Path(sys.executable).with_name("pythonw.exe") if os.name == "nt" else Path(sys.executable)
    if not executable.exists():
        executable = Path(sys.executable)
    with CONSOLE.open("a", encoding="utf-8") as output:
        process = subprocess.Popen([str(executable), "dsh_feishu_service.py"], cwd=ROOT,
            env=env, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
            start_new_session=os.name != "nt", close_fds=True)
    PID_FILE.write_text(json.dumps({"pid": process.pid, "startedAt": time.time()}, indent=2), encoding="utf-8")
    print(json.dumps({"status": "started", "pid": process.pid}))
    return 0


def status() -> int:
    pid = saved_pid()
    running = alive(pid)
    print(json.dumps({"status": "running" if running else "stopped", "pid": pid}))
    return 0 if running else 1


def stop() -> int:
    pid = saved_pid()
    if alive(pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        else:
            os.killpg(pid, signal.SIGTERM)
    print(json.dumps({"status": "stopped", "pid": pid}))
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    raise SystemExit({"start": start, "status": status, "stop": stop}[command]())
