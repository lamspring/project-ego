"""Run one isolated DSH session without exposing credentials or mixing workers."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

from dsh_ego_launcher import DSH, dsh_environment

ROOT = Path(__file__).resolve().parent


def run_dsh(prompt: str, session_file: Path, timeout: int = 1800) -> dict:
    env = dsh_environment()
    command = [str(DSH), "--profile", "ego-a", "--json"]
    if session_file.exists():
        session_id = json.loads(session_file.read_text(encoding="utf-8")).get("sessionId")
        if session_id:
            command.extend(["--session-id", session_id])
    command.append(prompt)
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8",
                            capture_output=True, timeout=timeout)
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    session_id = next((e.get("sessionId") for e in events if e.get("type") == "session"), None)
    if session_id:
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps({"sessionId": session_id}, indent=2), encoding="utf-8")
    final = next((e.get("text", "") for e in reversed(events) if e.get("type") == "final"), "")
    if result.returncode or not final.strip():
        raise RuntimeError(f"DSH failed ({result.returncode}): {result.stderr or result.stdout}")
    return {"text": final.strip(), "sessionId": session_id}
