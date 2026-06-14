# 事件、两阶段 Tick 与规则决策契约

状态：Frozen for Step 15-17  
生效日期：2026-06-14

## 1. WorldEvent 与 WorldLog

- `WorldEvent` 是已经发生的客观事实，不包含 Agent 的主观决策理由。
- 每个成功 ActionResult 必须包含至少一个 WorldEvent。
- WorldEvent 通过 `source_action_id` 追溯到 ActionProposal；ActionResult 通过 `events` 追溯到 WorldEvent。
- 环境天气实际变化也产生无 `source_action_id` 的客观事件。
- `summary` 只用于阅读；规则判断必须使用 `event_type`、participants 和 facts。
- `WorldLog` 仅允许 Environment 追加，事件 ID 必须严格递增。
- JSONL 持久化禁止静默覆盖，并保持事件顺序。
- 失败 ActionResult 不得写入伪装成成功的 WorldEvent。

## 2. 两阶段 Tick

每个规则 tick 必须：

1. 执行当前 time block 的环境变化。
2. 生成统一只读 WorldSnapshot。
3. 从同一快照为所有 Agent 构建 Observation。
4. 收集全部 ActionProposal，期间禁止修改 WorldState。
5. 统一校验并按 seed 控制的稳定优先级解决冲突。
6. 按稳定顺序提交接受的行为并写入 WorldLog。
7. 增加 tick 并推进统一时钟。

若 tick 中途失败，必须恢复：

- WorldState。
- DeterministicRandom。
- DeterministicIdGenerator。
- WorldLog。

## 3. 冲突规则

- 每个 Agent 在一个 tick 只能提交一个行为。
- talk 会同时占用发起者和目标人物的行为资源。
- 冲突提案先按稳定 action ID 获得 seed 控制优先级，再确定赢家。
- 冲突失败返回明确 ActionResult，不产生成功事件。

## 4. 规则决策

- `RuleDecisionPolicy` 选择分数最高的候选行为。
- 每次决策产生 `DecisionAudit`，保存 Observation、候选集合、选择结果、提案和 fallback 标记。
- 决策理由只进入 ActionProposal 与审计记录，不进入 WorldEvent facts。
- 无候选时明确 fallback 为 stay。
- 规则决策不调用真实 LLM。

## 5. 运行模式

- 完整规则模拟包含六个 Agent。
- world 模式使用相同 WorldRuntime 和两阶段 tick，但排除小说家、Recorder 与 Writing。
- 两种模式均产生客观 WorldLog，并可按固定 seed 重放。
