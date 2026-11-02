"""Persistent semantic Router: batch routing and unified external wording only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dsh_process import ROOT, run_dsh

SESSION = ROOT / "reports" / "dsh-router-session.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", help="JSON file containing pending trigger summaries")
    parser.add_argument("--notify", help="finished Work Item ID")
    args = parser.parse_args()
    if bool(args.batch) == bool(args.notify):
        raise SystemExit("exactly one of --batch or --notify is required")
    if args.batch:
        payload = json.loads(Path(args.batch).read_text(encoding="utf-8"))
        prompt = (
            "你是 EGO-A 唯一连续主体的常驻 Router，只负责人际交互、全局协调和分派，不亲自执行任务。\n"
            "先 wake、sync。下面是本批已持久化、尚未路由的 Trigger；一次处理整批，不得重复 ingest。\n"
            "只对明确属于现有 Work Item 范围的事件用 direct；新主题即使来自同一 DM 也用 new；无必要行动可 ignore。\n"
            "每个 Trigger 必须调用 route 并保留理由；new 提供可独立执行的 title/brief/priority。\n"
            "不得 claim、heartbeat、finish，不得执行 Work Item 的具体工作，不向主人输出进度或结果。\n"
            "完成后只输出 routed 数量。\n" + json.dumps(payload, ensure_ascii=False)
        )
    else:
        prompt = (
            "你是 EGO-A 的 Router。一个隔离 Worker 已结束，只允许 recall 该 Work Item 并核对真实状态。\n"
            "根据持久结果给主人一段不超过100词的简洁中文交付：结论、关键证据、必要限制；不得暴露推理或工具流水。\n"
            "若状态是 waiting，只说明需要什么；failed 不得包装成成功；cancelled 如实说明。\n"
            "不要执行新任务，不要修改状态。\n" f"work_id={args.notify}"
        )
    result = run_dsh(prompt, SESSION)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
