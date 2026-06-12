# MVP-0.1 架构契约

状态：Frozen for Step 02  
生效日期：2026-06-12

## 1. 数据所有权

| 数据 | 唯一所有者 | 允许读取者 | 允许修改者 |
| --- | --- | --- | --- |
| 时间、天气、地点状态 | Environment | Environment、Perception | Environment |
| Agent 客观位置和身体状态 | Environment | Environment、Perception | Environment |
| WorldEvent 与 WorldLog | Environment / EventLog | Environment、Perception、审计工具 | Environment / EventLog |
| Observation 与 ObservedEvent | Perception | 对应 Agent、Recorder、审计工具 | Perception |
| Agent 习惯、目标、记忆、关系认知 | 对应 Agent | 对应 Agent、受控审计工具 | 对应 Agent |
| 小说家 ObservationLog 与 ExperienceLog | Recorder | Recorder、Writing、审计工具 | Recorder |
| 日记、小说片段、章节 | Writing / Storage | 用户、审计工具 | Writing / Storage |

## 2. 禁止访问与禁止修改

- Agent 禁止读取或修改完整 WorldState。
- Agent 禁止直接修改客观位置、天气、时间和 WorldLog。
- NovelistAgent 禁止拥有专用全知接口。
- Recorder 禁止读取 WorldLog。
- Writing 禁止读取 WorldLog 或 WorldState。
- Writing 禁止修改任何世界或 Agent 状态。
- Perception 禁止创造或修改客观 WorldEvent。
- app 编排层禁止绕过 Environment 提交行为。

## 3. 当前地点契约

Agent 当前地点的权威值只存在于 WorldState。

- Agent 可以从 Observation 知道自己当前所在地点。
- Agent 不保存另一个可独立修改的权威当前位置。
- 所有移动都必须通过 ActionProposal 和 Environment 提交。

## 4. 事件契约

- ActionProposal 是意图，不是事实。
- ActionResult 表示提案是否被接受及其结果。
- WorldEvent 只记录已经客观发生的事情。
- ObservedEvent 是特定 Agent 对 WorldEvent 的认知版本。
- WorldEvent 与 ObservedEvent 必须使用不同数据类型和日志。
- 自然语言摘要不能替代结构化事实字段。

## 5. Tick 事务契约

每个 tick 必须使用两阶段流程：

1. 基于同一个只读世界版本生成全部 Agent 的 Observation。
2. 全部 Agent 只基于各自 Observation 提出 ActionProposal。
3. 收集完成后统一校验和解决冲突。
4. Environment 原子提交被接受的行为。
5. 生成 WorldEvent 并写入 WorldLog。
6. Perception 将事件分发为各 Agent 的 ObservedEvent。
7. Agent 更新记忆，小说家 Recorder 记录材料。
8. 完成 checkpoint 后推进时间。

提案收集阶段禁止修改 WorldState。

## 6. 模块依赖方向

允许的高层依赖方向：

`core <- simulation/events/actions/perception/agents/memory <- writing/storage <- app`

具体约束：

- `core` 不依赖领域模块。
- `simulation` 不依赖 `writing`。
- `agents` 依赖 Observation 和 ActionProposal 契约，不依赖可修改 WorldState。
- `perception` 只读取世界快照和客观事件。
- `writing` 只依赖小说家材料、LLM 抽象和 storage。
- `app` 只负责组装和生命周期编排。

## 7. 运行模式

### world

无小说家、无 Recorder、无 Writing。只验证世界独立运行。

### observe

包含小说家和 Recorder，不生成文学文本。

### full

世界、小说家记录和 Writing 全部启用。

三种模式必须复用同一个 World Runtime。

## 8. 架构退出门槛

- 不存在 Agent 与 WorldState 的位置双真源。
- 不存在 DiaryWriter 或 ChapterWriter 读取 WorldLog 的路径。
- 不存在小说家专用全知入口。
- 不存在边观察边提交行为的单阶段 tick。
- 不存在 Writing 反向修改世界的路径。
