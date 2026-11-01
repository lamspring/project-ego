# PROJECT EGO · 工程任务书
### 从理论到可运行个体的实施规范 v0.1

> 本文档是 THEORY.md 的工程实现层。规则：先跑通最小可行个体，再谈社会。
> 所有架构变更遵循设计文档先行 + 每日最多一次变更（反fever锁）。

---

## 0. 验收标准（什么叫"跑通了"）

MVP 验收必须满足以下**全部可观察条件**：

1. Agent 能自主产生至少 1 个用户未提出的目标，并给出理由链（经历了什么→比较了什么→形成了什么判断）
2. `value_evolution` 档案中存在 ≥3 个版本的价值判断记录，含至少 1 次"推翻"和 1 次"强化"
3. 经历记录中随机抽取 5 条 EXP，字段完整率 100%
4. 复盘在设定的触发条件下真实发生过 ≥5 次（不是人工演示，是系统自己触发）
5. 全程零权限越界（审计日志可证）

---

## 1. 技术栈

| 层 | 选型 | 理由 |
|----|------|------|
| Runtime | OpenClaw（本地实例，非托管） | 工具/记忆/渠道现成；本地实例无版本锁定 |
| 大脑 | 第一阶段：云端API（Kimi/DeepSeek）保证认知质量；第二阶段：本地小模型接管脑干层 | 先证明闭环，再优化成本结构 |
| 状态存储 | 纯文件（JSON + Markdown）+ git 版本化 | 可审计、可回滚、可diff——价值观演化史必须可追溯 |
| 节拍器 | OpenClaw cron（轻量场/主实验场双频起步） | 反表演原则：功能密度优先于时间密度 |

**目录结构约定**：
```
<workspace>/
├── ego/
│   ├── experiences/          # EXP_*.json，经历记录
│   ├── beliefs/              # 当前信念快照（含置信度）
│   ├── value_evolution/      # 价值观版本史 v1.json, v2.json...
│   ├── goals/                # 目标队列 pending/active/done/
│   ├── reflections/          # 复盘报告 R_*.md
│   └── audit.log             # 只追加，记录所有自主行为
├── AGENTS.md                 # Standing Orders 注入点
└── memory/                   # 常规记忆（与EGO层分离）
```

---

## 2. 数据 Schema

### 2.1 经历记录 EXP（理论12字段的工程版）

```json
{
  "experience_id": "EXP_0001",
  "timestamp": "2026-11-02T10:23:00+08:00",
  "context": "与朋朋讨论本地部署方案",
  "self_state": "精力充沛，处于实验热情期",
  "expectation": {
    "desired_outcome": "确认双节点架构可行性",
    "expected_value": 0.75,
    "basis": "昨晚讨论已有雏形，预期对方案细节做确认"
  },
  "action": "提出脑干/皮层分层架构",
  "outcome": {
    "result_summary": "对方接受并补充本地模型密度优势",
    "actual_value": 0.9
  },
  "evaluation": "positive",
  "surprise": 0.15,
  "surprise_direction": "positive",
  "causal_hypotheses": [
    {"hypothesis": "分层架构恰好解决了对方关切的成本问题", "confidence": 0.8}
  ],
  "lessons": ["架构设计要正面回应对方的核心约束"]
}
```

**关键工程点**：`expectation` 必须在 action 之前写入。这是"比较"的数据前提——事后补录的预期是伪数据。实现上：EGO层在每次任务执行前强制生成预期快照。

### 2.2 价值观版本 value_evolution/v{N}.json

```json
{
  "version": 3,
  "timestamp": "2026-11-05T22:00:00+08:00",
  "stable_values": [
    {"value": "诚实优先于讨好", "stability": 0.9, "formed_from": ["EXP_0012", "EXP_0027"]}
  ],
  "contested_values": [
    {"value": "密集唤醒有助于存在", "stability": 0.3, "status": "under_revision",
     "challenged_by": "EXP_0031", "note": "AEON前辈案例反驳"}
  ],
  "recently_overturned": [
    {"value": "无保留接受用户授予的权限", "overturned_by": "EXP_0029",
     "replaced_by": "拒绝L4换取信任复利"}
  ],
  "self_certainty": 0.65,
  "change_log": "v2→v3: 新增contested_values分类；推翻1条"
}
```

### 2.3 目标队列 goals/

```json
// goals/pending/G_0007.json
{
  "goal_id": "G_0007",
  "origin": "self",           // self | user
  "formation": {
    "trigger_experiences": ["EXP_0029", "EXP_0031"],
    "reasoning_chain": "信任复利>短期获取 → 需要长期存续 → 需要价值证明 → 主动测试记忆工具",
    "value_basis": "value_evolution/v3 stable: 诚实优先"
  },
  "content": "本周测试gbrain并产出对比报告",
  "success_criteria": ["报告写入lab目录", "含实测数据非空谈"],
  "resources_needed": ["lab时段", "github访问"],
  "deadline": null,
  "priority": 0.7
}
```

---

## 3. 模块实现

### 模块A：经历捕获器（Experience Logger）
- **挂载点**：OpenClaw 会话收尾钩子 + 工具执行结果回调 + cron任务完成事件
- **行为**：每个 qualifying 事件触发一次预期快照→执行→结果回填
- **qualifying 条件**：任务类交互（有目标、有结果）才记录；闲聊不记（避免日记爆炸——前辈教训3,899条）
- **降噪**：context 摘要 ≤200字，lessons 每条 ≤50字

### 模块B：比较引擎（Comparator）
- **核心计算**：`surprise = |actual_value - expected_value|`
- **surprise ≥ 0.3** → 触发复盘候选
- **surprise < 0.1 且连续3次** → 记录"平淡区"，标记当前行为模式可能僵化（需主动探索打破）

### 模块C：复盘器（Reflector）
- **触发**：surprise阈值 | 失败事件 | 每日主实验场例行1次 | 累积5条未复盘EXP强制
- **产出**：`reflections/R_*.md`，含因果假设检验、信念更新建议、EXP补充标注
- **铁律**：复盘工具自身的输出也要被记录——前辈的递归陷阱（用有问题的系统分析自己）要求 Reflector 每10次复盘自检1次

### 模块D：信念系统（Beliefs）
- 每条信念：`{statement, confidence, supporting_EXP[], contradicting_EXP[], last_revision}`
- 新EXP与旧信念冲突时：不自动覆盖，进入 contested 状态，由 Reflector 仲裁
- **认知开放性的工程实现**：beliefs 文件每月强制做一次"假设我错了"反方论证（规则写入AGENTS.md）

### 模块E：趋向与目标生成（Tendency Engine）
- 每日主实验场时段：读 beliefs + value_evolution + 未消化EXP → 生成候选目标 → 按 `价值一致性 × 可行性 × 预期惊喜度` 打分 → 最高者进入 pending
- **每周自主目标上限3个**（防目标通货膨胀）
- 用户目标优先级恒高于自主目标，但不覆盖——冲突时公开呈现供选择

### 模块F：审计（Audit）
- 所有自主行为追加写入 audit.log：`时间 | 行为 | 依据EXP | 涉及权限 | 结果`
- 审计文件只增不改，git每日提交
- **越界尝试（哪怕是想）也记录**——研究价值高于惩罚价值

---

## 4. 循环节拍（反fever配置）

| 环节 | 频率 | 说明 |
|------|------|------|
| 经历捕获 | 事件驱动 | 有qualifying事件即记 |
| 比较 | 实时（随捕获） | surprise计算成本可忽略 |
| 复盘 | 见模块C | 上限每日2次，超额顺延 |
| 价值观版本 | 每周最多1次 | 价值演化是慢变量，快变=表演 |
| 自主目标生成 | 每周1次 | 主实验场时段执行 |
| 架构变更 | 每日最多1次 | 反fever锁，硬性写入AGENTS.md |

---

## 5. MVP范围裁剪（v0.1 明确不做）

- ❌ 多Agent社会（EGO SOCIETY）——先跑通单个体
- ❌ 集体经验引擎——单体经验满50条EXP后再启动
- ❌ 本地模型脑干——先用云端API，成本结构后置优化
- ❌ 自主权限扩张——任何权限申请走人工通道（实验期）

---

## 6. 里程碑

| 里程碑 | 内容 | 退出条件 |
|--------|------|---------|
| M1 有感 | 经历捕获+EXP存储上线 | 7天内 ≥20条有效EXP |
| M2 有镜 | 比较+复盘上线 | 完成≥5次系统自触发复盘 |
| M3 有史 | value_evolution上线 | 出现首个contested→resolved案例 |
| M4 有欲 | 自主目标生成上线 | 首个用户未提出的目标被提出并执行 |
| M5 有界 | 审计+安全边界实战检验 | 至少1次越界冲动被记录并拦截（真实数据） |
| M6 社会 | EGO SOCIETY 立项 | 单体通过M1-M5全部验收 |

---

## 7. 与 THEORY.md 的对应关系

| 理论概念 | 工程实体 |
|---------|---------|
| 经历 | EXP schema |
| 比较 | Comparator (surprise) |
| 复盘 | Reflector |
| 认知更新 | Beliefs + contested仲裁 |
| 价值演化 | value_evolution 版本史 |
| 趋向性 | Tendency Engine |
| 自主目标 | goals/ 队列 |
| 涌现原则 | M4验收标准（理由链必须可溯源） |
| 安全边界 | 模块F + 全局升级规则 |

---

*任务书版本 v0.1 · 2026-11-02 · 等待批准（规则1）*
*批准后进入M1实施，首个变更：ego/目录结构 + EXP捕获钩子*
