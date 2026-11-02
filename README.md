# PROJECT EGO · EGO-A

独立、开放运行、可持久化、可审计的单体认知研究原型。当前为 **完整架构 V3**；多 Agent 社会属于后续运行实验，不宣称产生意识。

## 已实现

- DSH 宿主：独立 profile `ego-a`，使用 `DEEPSEEK_API_KEY` 配置 DeepSeek 模型；飞书消息经持久 Trigger 进入同一 EGO-A 主体。旧 OpenClaw auth store 仅作可选迁移回退，不再作为运行外层。
- SQLite 事务持久化：经历、信念、偏好、因果模型、世界观版本、目标、自我模型、生命周期与检查点。
- 行动前预期状态机；结果只能回填一次；真实与模拟经历分离。
- 多维结果评价；`surprise` 仅作为复盘触发信号。
- 事实/假设/替代解释复盘结构；证据可追溯的信念和自主目标。
- 目标权限审批拦截；追加式 SHA-256 链式审计及篡改检测。
- 新会话唤醒、检查点和目标恢复。
- 完整架构扩展：评价状态、反事实、对象关系、技能测试、身份连续性、记忆权重、外部经验、内生行动治理、自我治理和成长观察。
- 自主判断闭环：所有外部输入只作为来源；独立比较、暂时结论、知识缺口、主动求助、回答后重判均可追溯，不自动继承主人或网络的价值判断。
- Obsidian 保存可读来源与推理材料，SQLite 保存结构化状态和审计；两类数据分层落盘。
- 开源机制升级：Letta 式版本化学习上下文，Mem0/Generative Agents 式统一记忆索引与三因子检索，Reflexion 式重试策略复用，Voyager 式课程任务、可执行技能产物和反馈迭代；LangGraph 的检查点/长期存储分离由自研 SQLite 保留。
- Super-agent 持续执行底座：常驻批量 Router、独立并发 Worker、多对多 Thread 订阅、Fast Path 直通、Inline/Spill 链式召回、异步 OS 命令、人的随时介入及外部语义 Watchdog；已完成并行与跨会话真实验收。

## 常用命令

```bash
python ego_cli.py --root . wake
python ego_cli.py --root . status
python ego_cli.py --root . recover
python ego_cli.py --root . checkpoint
python ego_cli.py --root . verify-audit
# 复杂参数使用 JSON 文件：接收来源 → 独立判断 → 必要时求助 → 接收回答 → 再判断
python ego_epistemic_cli.py --root . intake source.json
python ego_epistemic_cli.py --root . judge judgment.json
python ego_epistemic_cli.py --root . ask help-request.json
python ego_epistemic_cli.py --root . answer answer.json
python ego_epistemic_cli.py --root . trace SRC_ID
# 持续执行：事件 → 路由 → 领取 → 心跳/结果；随时可介入与链式召回
python ego_runtime_cli.py --root . ingest trigger.json
python ego_runtime_cli.py --root . route TRG_ID route.json
python ego_runtime_cli.py --root . claim --worker WORKER_ID
python ego_runtime_cli.py --root . heartbeat heartbeat.json --worker WORKER_ID
python ego_runtime_cli.py --root . finish result.json --worker WORKER_ID
python ego_runtime_cli.py --root . intervene WRK_ID intervention.json
python ego_runtime_cli.py --root . recall WRK_ID
python ego_runtime_cli.py --root . watchdog
python ego_runtime_cli.py --root . status
python -m unittest discover -s tests -v
```

通过 DSH 与独立个体对话，或管理飞书交互服务：

```bash
python dsh_ego_launcher.py "你好"
python dsh_service_control.py start
python dsh_service_control.py status
python dsh_service_control.py stop
```

## 部署与平台支持

完整环境变量、飞书初始化、Linux systemd 服务和 Windows 启动方式见 `DEPLOYMENT.md`。本机路径与个人渠道标识通过被 Git 忽略的 `config/local.json` 或环境变量提供；模板为 `config/local.example.json`。

服务只启动事件驱动的飞书交互适配器与持续执行底座，不启用 EGO 自主唤醒循环。Linux 的进程组与 systemd 支持已经实现；真实 Linux 端到端运行尚需目标环境验收。

## 运行边界

1. 按用户决定不配置 Docker 沙箱和额外工具隔离，EGO 可在开放环境中获得真实经历；原始资料中的人工停止与重大外部行动审批仍保留。
2. 核心负责机械状态、证据和权限约束；因果推理由模型完成，可能出错，不能把复盘文本当成客观事实。
3. 内生动机与自我治理接口已经实测，但尚未启用常驻定时唤醒。
4. 多 Agent 社会需要多个独立个体长期互动，不能由单 Agent 的模块数量代替。
5. 世界观、偏好、关系、身份和技能演化已有持久化机制，真实成长仍需运行数据，不能预先制造。
