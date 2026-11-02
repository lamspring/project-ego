"""Configure the official Lark CLI from environment variables on Windows or Linux."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from ego_host import executable

LARK = executable("lark-cli", "LARK_BIN")


def main() -> None:
    app_id = os.environ.get("FEISHU_APP_ID")
    secret = os.environ.get("FEISHU_APP_SECRET")
    if not app_id or not secret:
        raise RuntimeError("Set FEISHU_APP_ID and FEISHU_APP_SECRET for setup only")
    env = os.environ.copy()
    env["LARKSUITE_CLI_CONFIG_DIR"] = os.environ.get("LARKSUITE_CLI_CONFIG_DIR", str(Path.home() / ".lark-cli-ego-a"))
    subprocess.run([LARK, "config", "init", "--app-id", app_id,
        "--app-secret-stdin", "--brand", "feishu"], input=secret, text=True, env=env, check=True)
    subprocess.run([LARK, "config", "strict-mode", "bot", "--global"], env=env, check=True)
    subprocess.run([LARK, "whoami"], env=env, check=True)


if __name__ == "__main__":
    main()
