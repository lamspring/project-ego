"""Launch EGO-A's DSH profile on Windows or Linux without exposing credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from ego_host import executable, setting

HOME = Path.home()
AUTH = HOME / ".openclaw" / "agents" / "ego-a" / "agent" / "openclaw-agent.sqlite"
DSH = executable("dsh", "DSH_BIN", HOME / "AppData" / "Roaming" / "kimi-desktop" / "daimon-share" / "daimon" / "npm-global" / "dsh.cmd")


def deepseek_key() -> str:
    """Prefer DEEPSEEK_API_KEY; legacy local store is only an optional migration aid."""
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ["DEEPSEEK_API_KEY"]
    if AUTH.exists():
        with sqlite3.connect(f"file:{AUTH.as_posix()}?mode=ro", uri=True) as db:
            rows = db.execute("SELECT store_json FROM auth_profile_store").fetchall()
        profiles = {}
        for (raw,) in rows:
            data = json.loads(raw)
            profiles.update(data.get("profiles", data))
        profile = profiles.get("deepseek:manual", {})
        for field in ("key", "apiKey", "token"):
            value = profile.get(field)
            if isinstance(value, str) and value:
                return value
    raise RuntimeError("Set DEEPSEEK_API_KEY in the service environment")


def dsh_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["DEEPSEEK_API_KEY"] = deepseek_key()
    env.setdefault("DSH_PERMISSION_MODE", "danger-full-access")
    node_dir = setting("EGO_NODE_DIR")
    legacy_node = HOME / ".openclaw" / "node"
    if node_dir or legacy_node.exists():
        env["PATH"] = str(node_dir or legacy_node) + os.pathsep + env.get("PATH", "")
    return env


def main() -> int:
    args = [DSH, "--profile", "ego-a", *sys.argv[1:]]
    return subprocess.run(args, env=dsh_environment()).returncode


if __name__ == "__main__":
    raise SystemExit(main())
