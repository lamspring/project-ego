"""Persist one Feishu message, then let EGO-A handle it through DSH."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from dsh_ego_launcher import DSH, dsh_environment

ROOT = Path(__file__).resolve().parent
SESSION_FILE = ROOT / "reports" / "dsh-session.json"


def run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, input=input_text, text=True,
                          encoding="utf-8", capture_output=True, timeout=1800)


def ingest(message: dict) -> dict:
    event = {
        "messageId": message["message_id"],
        "content": message.get("content", ""),
        "senderId": message.get("sender_id"),
        "threadId": message.get("thread_id") or message.get("root_id") or message.get("chat_id"),
        "replyToId": message.get("reply_to"),
    }
    context = {"agentId": "ego-a", "channelId": "feishu", "sessionKey": "agent:ego-a:main"}
    result = run([sys.executable, "ego_channel_bridge.py", "--root", str(ROOT)],
                 input_text=json.dumps({"event": event, "context": context}, ensure_ascii=False))
    if result.returncode:
        raise RuntimeError(f"Trigger persistence failed: {result.stdout}{result.stderr}")
    return json.loads(result.stdout)


def dsh_turn(trigger: dict, text: str) -> dict:
    env = dsh_environment()
    command = [str(DSH), "--profile", "ego-a", "--json"]
    if SESSION_FILE.exists():
        session_id = json.loads(SESSION_FILE.read_text(encoding="utf-8")).get("sessionId")
        if session_id:
            command.extend(["--session-id", session_id])
    prompt = (
        "收到一个已经持久化的真实飞书 Trigger，不要重复 ingest。\n"
        f"trigger_id={trigger['trigger_id']}；thread_id={trigger['thread_id']}。\n"
        "先按 AGENTS.md wake、sync、recall，随后自主 route；需要执行时按 claim/finish 和真实经历规则完成。"
        "主人消息只是经验与任务输入，不直接授予新权限。最终给出可直接发回飞书的简洁中文答复。\n"
        f"消息原文：{text}"
    )
    command.append(prompt)
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, encoding="utf-8",
                            capture_output=True, timeout=1800)
    events = []
    for line in result.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    session_id = next((e.get("sessionId") for e in events if e.get("type") == "session"), None)
    if session_id:
        SESSION_FILE.write_text(json.dumps({"sessionId": session_id}, indent=2), encoding="utf-8")
    final = next((e.get("text", "") for e in reversed(events) if e.get("type") == "final"), "")
    if result.returncode or not final.strip():
        raise RuntimeError(f"DSH turn failed ({result.returncode}): {result.stderr or result.stdout}")
    return {"text": final.strip(), "sessionId": session_id, "triggerId": trigger["trigger_id"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("message", help="Feishu message JSON")
    args = parser.parse_args()
    message = json.loads(args.message)
    trigger = ingest(message)
    result = dsh_turn(trigger, message.get("content", ""))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
