# EGO-A 开源机制选型与落地记录

日期：2026-11-02

## 原则

不叠加六套运行框架，不引入重复状态源。当前采用 DSH、SQLite、Obsidian 和自研认知状态机，只移植经源码核对的关键机制。

## 逐项选型

| 项目 | 核对资料 | 采用机制 | 未采用部分与原因 |
|---|---|---|---|
| Letta | https://docs.letta.com/guides/agents/architectures/sleeptime | 后台整理、容量受限的学习上下文、版本和证据链、原始历史保留 | 不引入独立 Letta Agent 和第二套记忆块存储 |
| Mem0 | https://docs.mem0.ai/open-source/python-quickstart | 统一记忆索引、来源元数据、实体/时间过滤、检索与历史融合入口 | 不引入 Qdrant/OpenAI 默认依赖；当前 hashed-ngram 是词法向量，不是神经嵌入 |
| LangGraph | https://langchain-ai.github.io/langgraph/concepts/persistence/ | Checkpointer 管运行恢复，长期 Store 管跨会话记忆，二者职责分离 | 现有 SQLite 状态机已覆盖需求，暂不增加 LangGraph 编排依赖 |
| Generative Agents | `persona/cognitive_modules/retrieve.py` | recency/importance/relevance 归一化，0.5/2/3 权重，访问后更新 last_accessed | 不复制模拟小镇、固定日常计划或类人行为表演 |
| Voyager | `voyager/agents/curriculum.py`、`skill.py` | 完成/失败课程历史、状态证据、技能描述、可执行产物、反馈迭代 | 不引入 Minecraft/Mineflayer；技能仍须 EGO 的真实测试门槛 |
| Reflexion | `programming_runs/reflexion.py` | 执行反馈→语言反思→下一次尝试携带策略→再次测试 | 不把自评当客观奖励；必须有真实执行结果或外部证据 |

## 实现映射

- `ego_memory_engine.py`：`memory_items`、`memory_blocks`、`memory_block_versions`、`reflection_strategies`。
- `ego_learning.py`：`curriculum_tasks`、`skill_artifacts`、`skill_iterations`。
- `ego_memory_engine_cli.py`：同步、检索、整理、策略保存和重试上下文。
- `ego_learning_cli.py`：课程提出/选择/回填、技能产物与迭代记录。
- `AGENTS.md`：将检索、反思复用、课程与技能产物接入每次认知作业。
- 自主目标唤醒循环保持停用；持续服务只处理环境 Trigger 和已分派任务。

## 验证证据

- 31 项项目回归测试通过。
- 实际记忆检索中，EXP_0001 早期信息缺失失败对相关问题排名第一，学习上下文同时召回。
- 字段核对技能经第二次真实测试后 validated，并关联 `checklists/field_check.py`。
- 第二次无人提示运行完成 EXP_0004：选择并完成 CUR_515ea4b137，修复 2 个真实边界缺陷，新增 24 项边界断言。
- 独立复核：24 项边界断言、原 demo 和 31 项回归均通过。
- 课程任务标记 completed，技能边界测试产物 SA_1312547804 已登记，下一次策略 RS_09c514bbae 已保存。

## 后续缺口

1. 接入可替换的神经嵌入提供者，与当前词法向量做召回对照测试。
2. 增加记忆压缩和重复聚类的质量评估，避免整理结果污染原始证据。
3. 对“读取反思”与“屏蔽反思”做同类任务对照，验证反思是否真实改善结果。
4. 课程选择权重仍需长期数据校准，不能把固定评分当成已形成偏好。
