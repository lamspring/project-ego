# EGO-A Super-agent 持续执行底座落地与验收

日期：2026-11-02

依据 DeepSeek Harness 团队《Super-agent 设计探索：迈向更自主的 Agent 系统》逐项改造。Router 与 Worker 是同一 EGO-A 的职责层和执行上下文，不是多个人格。

## 机制落地

| 原文机制 | EGO-A 当前实现 | 验证状态 |
|---|---|---|
| 常驻 Router | `dsh_ego_router.py` 持久 Router Session；只负责批量语义路由和统一交付措辞，不执行 Worker 任务 | 已真实运行 |
| 隔离 Worker | `dsh_ego_worker.py` 每个 Work Item 独立 DSH Session，最多三个并发；Worker 不直接回复主人 | 已真实运行 |
| Router 批处理 | `dsh_continuous.py` 每批最多读取 50 个 pending Trigger，一次交给 Router | 两个事件同批真实路由 |
| 两级过滤 | 飞书主人 DM/消息类型程序过滤，Router 语义决定 ignore/new/direct | 已接入 |
| Thread 订阅直通 | 已订阅 Thread 由程序 Fast Path 直通，无需再次模型路由 | 已接入并测试 |
| 多对多订阅 | `thread_subscriptions(thread_id,work_id)` 复合主键；同一 DM 可并行多个主题，同一事件可投递多个 Worker | 自动化测试通过 |
| Inline & Spill | Router 只注入摘要；长文本截断并保留 `recall-trigger` 续读入口；recall 内联下一跳 Work ID | 自动化测试通过 |
| 全双工异步 ReAct | `ego_async_cli.py start/poll/output/stop`；WMI 创建独立 OS 进程，退出码、输出和状态落 SQLite | 跨 DSH 会话真实通过 |
| 人的介入 | redirect/pause/resume/cancel 与 revision 防旧 Worker 回写 | 自动化测试通过 |
| 存算与环境解耦 | DSH 计算进程、SQLite 事实源和独立 OS 执行进程分离；本机执行环境保留 | 本机形态已运行；未做云端故障转移 |
| 外部 Watchdog | 独立 `dsh_watchdog_service.py` 检查租约和无进展；语义审查在独立 DSH Session | 失效重排已真实运行 |
| 克制输出 | Worker 只内部汇报，Router 统一生成 IM 短交付；无价值事件可 ignore | 已接入 |

## 真实验收证据

1. Router 将同一验证 Thread 中的两个事件分派为 `WRK_5a6ad86dd3` 与 `WRK_ce64869caf`，两个 Worker 真实并行领取和执行。
2. 后台任务 `JOB_4229d373c8` 与 `JOB_673ff14a06` 均返回 `exit_code=0`，分别输出 `WORKER_A_DONE`、`WORKER_B_DONE`。
3. 任务 B 的首次 Worker 失效后，外部 Watchdog 产生 `watchdog_requeue`；第二次领取后最终 `succeeded`，attempts=2。旧 revision 不得回写。
4. 严格跨会话异步验收：一个 DSH 会话启动 `JOB_9bb2bafcd3` 后退出；另一个全新会话读取到 `state=succeeded`、`exit_code=0`、`output=WMI_CROSS_CALL_OK`。
5. 结构化证据：`reports/dsh-continuous-evidence.json`；复核入口：`python reports/verify_continuous.py`。
6. 全量自动化回归：47/47 通过。

## 验收过程中修复的真实问题

- Windows 虚拟环境启动器提前退出曾造成重复 Worker 启动；增加排队启动宽限期，原子 claim 继续防止重复执行。
- DSH 默认 `workspace-write` 会回收后台后代进程并禁止 WMI；按主人既定开放权限要求，EGO-A 的 DSH 调用使用 `danger-full-access`。
- 普通 detached/VBS 方案未通过跨会话验收；最终由 Windows `Win32_Process.Create` 创建独立进程后才通过。失败记录保留，未改写为成功。

## 边界

- 这是本机可持续、事件驱动、并行执行和异常恢复底座，不是云端高可用服务；电脑关机或断网时不能继续执行。
- 长期语义路由质量、跨月记忆和多设备接管仍需长期真实运行数据。
- 自主目标唤醒循环仍停用；持续服务只响应环境 Trigger、执行已分派任务和进行 Watchdog 巡检。
- 不据此宣称意识、人类价值观或永不出错。
