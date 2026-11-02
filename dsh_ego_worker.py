"""One background Worker execution context; it never replies to external users."""
from __future__ import annotations

import argparse
from pathlib import Path

from dsh_process import ROOT, run_dsh


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("work_id")
    args = parser.parse_args()
    worker = f"ego-a:dsh-worker:{args.work_id}"
    prompt = (
        "你是 EGO-A 的隔离 Worker 执行上下文，不是新主体，不得直接联系主人。\n"
        "按 AGENTS.md 执行 wake、sync；只处理指定 Work Item，不读取其他 Worker 的会话。\n"
        f"先运行 python ego_runtime_cli.py --root . claim --worker {worker} --work-id {args.work_id} --lease 900。\n"
        "若返回 null，说明任务已被领取、改向或完成，直接结束，不得重复 claim。\n"
        "领取后读取 inbox，按需 recall；长命令必须用 ego_async_cli.py start/poll，禁止同步长时间阻塞。\n"
        "执行期间 heartbeat 报告实质进展；主人 redirect/pause/cancel 后旧 revision 不得回写。\n"
        "完成时用 finish 回填 succeeded/failed/waiting 和可审计结果；结果摘要是给 Router 的内部汇报，不是外部回复。\n"
        "最后输出一句内部完成摘要。\n"
        f"work_id={args.work_id}"
    )
    result = run_dsh(prompt, ROOT / "reports" / "workers" / f"{args.work_id}.json")
    print(result["text"])


if __name__ == "__main__":
    main()
