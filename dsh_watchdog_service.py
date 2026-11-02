"""External infrastructure watchdog process for the continuous execution plane."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from ego_core import Ego
from ego_runtime import Runtime

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "reports" / "dsh-watchdog.ndjson"


def record(kind, **data):
    with LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"at": time.time(), "kind": kind, **data}, ensure_ascii=False) + "\n")


def main():
    record("watchdog_start", pid=os.getpid())
    while True:
        try:
            with Ego(ROOT) as core:
                observations = Runtime(core).watchdog(stale_seconds=600)
            for observation in observations:
                record("observation", **observation)
                if observation["kind"] == "no_progress":
                    result = subprocess.run([sys.executable, "dsh_ego_watchdog.py",
                        observation["work_id"], observation["id"]], cwd=ROOT,
                        capture_output=True, text=True, encoding="utf-8", timeout=900)
                    record("semantic_review", workId=observation["work_id"], returnCode=result.returncode)
            record("watchdog_alive", observations=len(observations))
        except Exception as error:
            record("watchdog_failed", error=str(error))
        time.sleep(30)


if __name__ == "__main__":
    main()
