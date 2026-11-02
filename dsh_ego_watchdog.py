"""Semantic watchdog review for one observed lack of substantive progress."""
import argparse
from dsh_process import ROOT, run_dsh

p=argparse.ArgumentParser();p.add_argument('work_id');p.add_argument('observation_id');a=p.parse_args()
prompt=(
 "你是主系统之外的 EGO-A Watchdog 审查上下文，不是新人格。只检查指定 Work Item。\n"
 "先 recall，核对最近 heartbeat、Trigger 和任务目标，区分实际无进展与正常等待。\n"
 "只有持久证据证明偏离或需要介入时才可用 intervene；必须写具体理由，不得虚构失败，不得 finish 代替 Worker。\n"
 "若只是暂时无进展或证据不足，不修改状态。输出简短审查结论。\n"
 f"work_id={a.work_id} observation_id={a.observation_id}"
)
print(run_dsh(prompt,ROOT/'reports'/'dsh-watchdog-session.json')['text'])
