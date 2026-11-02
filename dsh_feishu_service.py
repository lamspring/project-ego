"""DSH-based Feishu ingress and idempotent reply service for EGO-A."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from ego_host import executable, setting

ROOT = Path(__file__).resolve().parent
HOME = Path.home()
LARK = executable("lark-cli", "LARK_BIN", HOME / "AppData" / "Roaming" / "kimi-desktop" / "daimon-share" / "daimon" / "npm-global" / "lark-cli.cmd")
LOG = ROOT / "reports" / "dsh-feishu.ndjson"
OWNER = setting("EGO_FEISHU_OWNER_OPEN_ID")
OWNER_CHAT = setting("EGO_FEISHU_OWNER_CHAT_ID")


def record(kind: str, **data: object) -> None:
    with LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps({"at": time.time(), "kind": kind, **data}, ensure_ascii=False) + "\n")


def lark_env() -> dict[str, str]:
    env = os.environ.copy()
    env["LARKSUITE_CLI_CONFIG_DIR"] = str(HOME / ".lark-cli-ego-a")
    return env


def reply(message_id: str, text: str, work_id: str = "router") -> None:
    result = subprocess.run([
        str(LARK), "im", "+messages-reply", "--message-id", message_id,
        "--text", text, "--idempotency-key", f"ego-{work_id}"[:50],
    ], cwd=ROOT, env=lark_env(), text=True, encoding="utf-8", capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Feishu reply failed: {result.stderr or result.stdout}")
    record("reply_sent", messageId=message_id, workId=work_id)


def handle(message: dict) -> None:
    sender = message.get("sender") or {}
    message["sender_id"] = message.get("sender_id") or sender.get("open_id") or sender.get("id")
    message["sender_type"] = message.get("sender_type") or (
        "bot" if sender.get("sender_type") in ("app", "bot") else "user")
    message_id = message.get("message_id") or message.get("id")
    if not message_id or message.get("sender_type") != "user":
        return
    if message.get("sender_id") != OWNER or message.get("chat_id") != OWNER_CHAT:
        record("ignored", messageId=message_id, reason="outside_owner_dm")
        return
    if not str(message.get("content", "")).strip():
        record("ignored", messageId=message_id, reason="empty")
        return
    record("message_received", messageId=message_id)
    result = subprocess.run([sys.executable, "-c",
        "import json,sys; from dsh_ego_turn import ingest; print(json.dumps(ingest(json.loads(sys.argv[1]))))",
        json.dumps(message, ensure_ascii=False)], cwd=ROOT, text=True, encoding="utf-8",
        capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    trigger = json.loads(result.stdout)
    record("trigger_persisted", messageId=message_id, triggerId=trigger["trigger_id"])


CURSOR = ROOT / "reports" / "dsh-feishu-cursor.json"


def messages(limit: int) -> list[dict]:
    result = subprocess.run([
        str(LARK), "im", "+chat-messages-list", "--chat-id", OWNER_CHAT,
        "--order", "desc", "--page-size", str(limit), "--no-reactions", "--json",
    ], cwd=ROOT, env=lark_env(), text=True, encoding="utf-8", capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"Feishu poll failed: {result.stderr or result.stdout}")
    answer = json.loads(result.stdout)
    return answer.get("data", {}).get("messages", [])


def position(message: dict) -> int:
    return int(message["message_position"])


def main() -> int:
    if not OWNER or not OWNER_CHAT:
        raise RuntimeError("Configure EGO_FEISHU_OWNER_OPEN_ID and EGO_FEISHU_OWNER_CHAT_ID")
    from dsh_continuous import ContinuousEngine
    engine = ContinuousEngine()
    watchdog = subprocess.Popen([sys.executable, "dsh_watchdog_service.py"], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt")
    record("service_start", pid=os.getpid(), mode="continuous_router_workers", watchdogPid=watchdog.pid)
    if CURSOR.exists():
        cursor = json.loads(CURSOR.read_text(encoding="utf-8"))["position"]
    else:
        latest = messages(1)
        cursor = position(latest[0]) if latest else 0
        CURSOR.write_text(json.dumps({"position": cursor}), encoding="utf-8")
    record("poll_ready", position=cursor)
    last_heartbeat = 0.0
    while True:
        if time.time() - last_heartbeat >= 60:
            record("poll_alive", pid=os.getpid(), position=cursor)
            last_heartbeat = time.time()
        try:
            batch = sorted((m for m in messages(50) if position(m) > cursor), key=position)
            for message in batch:
                handle(message)
                cursor = position(message)
                CURSOR.write_text(json.dumps({"position": cursor}), encoding="utf-8")
            engine.tick(reply)
            record("engine_alive", workers=len(engine.processes))
        except Exception as error:
            record("poll_failed", error=str(error))
        time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
