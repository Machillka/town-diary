# Runtime 与 Agent 基础契约

状态：Frozen for Step 10-12
生效日期：2026-06-13

## 1. World Runtime

- `WorldRuntime` 是 Environment 的生命周期入口。
- 生命周期状态为 `created`、`running`、`paused`、`ended`。
- 只有 `running` 状态可以推进 tick。
- 结束原因必须为 `completed` 或 `stopped`。
- world 模式不创建 Agent、Recorder 或 Writer，也不依赖 writing。
- `WorldTickRecord` 记录时间和天气等客观环境结果，但不替代 Step 15 的完整 WorldLog。

## 2. Runtime Checkpoint

组合 checkpoint 保存：

- RunContext manifest，包括 run ID、seed、配置摘要、随机数状态和 ID 状态。
- WorldStateCheckpoint，包括时间、天气、客观 Agent 状态和 tick。
- 已提交的 WorldTickRecord。
- 保存时生命周期状态和结束原因。
- schema version。

checkpoint 可在任意已提交 tick 后创建。恢复后，未结束的 runtime 统一处于 `paused`，必须显式调用 `resume()` 才能继续。

恢复与重放：

- 恢复必须验证当前配置摘要与原始运行一致。
- 恢复只读取结构化 checkpoint，不读取文本摘要或文学输出。
- 重放从原始 seed 和配置重新开始，并运行到 checkpoint 的 tick。
- checkpoint 文件禁止静默覆盖。

## 3. Agent 静态资料

每个 Agent 的静态配置包含：

- 身份、名称、role、住处。
- occupation 和 traits。
- 至少一个习惯及其时间、地点引用。
- 至少一个目标及其可选地点引用。
- 初始 mood、私有记忆和关系认知。

所有地点和 Agent 引用必须在配置加载阶段验证。

## 4. Agent 主观状态

- 小说家和居民使用同一个 `Agent` 类型，通过 `role` 区分。
- Agent 静态身份和资料不可变。
- 每个 Agent 独占自己的 `SubjectiveState`。
- 主观状态包含 mood、记忆和对其他 Agent 的关系认知。
- 对外只暴露冻结的 `SubjectiveStateSnapshot`。
- 主观状态变化不会修改 WorldState。

## 5. 客观信息边界

- Agent 不持有 WorldState、权威当前位置或权威身体状态。
- Agent 只能从属于自己的 `Observation` 读取当前客观位置和身体状态。
- Agent 不能使用其他 Agent 的 Observation。
- Agent 没有直接修改世界位置的方法。
