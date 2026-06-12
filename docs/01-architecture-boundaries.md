# 架构边界与数据所有权

## 1. 目标

本项目最重要的不是类数量，而是保证客观世界、Agent 主观认知和小说文本之间不会越权。本文档定义实现时必须保持的边界。

## 2. 建议的运行组成

### 2.1 World Runtime

World Runtime 是小镇环境本体，负责：

- 持有并推进客观 WorldState。
- 推进时钟和天气。
- 更新地点状态。
- 生成统一 tick 快照。
- 接收所有 Agent 的 ActionProposal。
- 校验行为、解决冲突并提交行为。
- 生成结构化 WorldEvent。
- 写入 WorldLog。
- 为感知系统提供只读世界快照和事件。

World Runtime 不负责：

- 写日记。
- 生成小说片段。
- 判断某个事件是否“适合剧情”。
- 为小说家提供额外真相。

### 2.2 Agent Runtime

Agent Runtime 负责每个居民的主观决策过程：

- 接收自己的 Observation。
- 更新个人记忆和信念。
- 根据习惯、需求、目标、关系认知和少量随机扰动评分候选行为。
- 产生一个 ActionProposal。

Agent Runtime 不负责：

- 直接修改 WorldState。
- 直接写入 WorldLog。
- 读取其他地点或其他 Agent 的隐藏状态。
- 决定行为已经成功发生。

### 2.3 Perception Pipeline

Perception Pipeline 是世界真相与 Agent 认知之间的唯一通道，负责：

- 根据 Agent 所在地点和感知规则生成 Observation。
- 把 WorldEvent 转换为特定观察者版本的 ObservedEvent。
- 区分直接观察、参与结果、传闻和不确定线索。
- 删除观察者无权知道的字段。

Perception Pipeline 不负责：

- 修改 WorldEvent。
- 创造新的客观事件。
- 修改 Agent 行为。
- 为写作系统直接读取 WorldLog 开后门。

### 2.4 Novelist Recorder

Recorder 是小说家 Agent 的记录能力，负责：

- 保存小说家实际收到的 Observation。
- 保存小说家实际获得的 ObservedEvent。
- 保存小说家的 Experience。
- 按天整理可供写作的材料。
- 保存材料来源 ID，支持后续追踪。

Recorder 不读取完整 WorldLog，也不把未观察事件复制到写作材料中。

### 2.5 Writing Pipeline

Writing Pipeline 是只读下游，负责：

- 从小说家当日材料生成日记。
- 从日记和可选关键场景生成小说片段。
- 从七天日记和片段整理章节。
- 输出文本及来源清单。

Writing Pipeline 不修改世界、不改变 Agent 状态、不直接读取 WorldLog。

## 3. 数据所有权

### 3.1 Environment 独占的客观状态

以下数据由 Environment 独占管理：

- day、time block、天气。
- 地点拓扑、开放状态和地点动态状态。
- Agent 的客观当前位置。
- Agent 的客观身体状态，例如能量、饥饿和是否能够继续行动。
- 当前 tick 的有效行为和冲突解决结果。
- WorldEvent、WorldLog。
- 随机数状态、事件 ID 和运行 seed。

这些数据只能通过环境规则或已提交 ActionResult 改变。

### 3.2 Agent 独占的主观状态

以下数据属于 Agent：

- 习惯偏好。
- 个人目标与行为倾向。
- 个人记忆。
- 对他人的关系认知。
- 对事件的解释、猜测和误解。
- 决策理由和候选行为评分。

Agent 可以更新自己的主观状态，但不能把主观判断直接写成客观世界事实。

### 3.3 只读投影

以下数据是从客观世界投影出的只读材料：

- Observation。
- ObservedEvent。
- 当前可用行为集合。
- Agent 可知的自身客观状态。

Agent 决策只能使用这些投影和自己的主观状态。

### 3.4 输出数据

以下数据属于输出与审计层：

- WorldLog。
- 每个 Agent 的观察或记忆审计记录。
- 小说家的 ObservationLog。
- 小说家的 ExperienceLog。
- 日记、小说片段和章节。
- simulation summary、来源清单和验收报告。

输出层不能反向修改运行状态。

## 4. 必须避免的双真源

### 4.1 Agent 当前地点

权威值只存在于 WorldState。Agent 通过 Observation 得知自己的地点。

### 4.2 时间和天气

权威值只存在于 Environment。Agent 不保存可以独立推进的个人时间或天气副本。

### 4.3 关系

需要区分：

- 客观互动历史：由 WorldEvent 表达。
- Agent 对关系的主观认知：由各 Agent 自己保存。

MVP 不应假设两个人对彼此拥有完全相同的关系值。

### 4.4 事件

WorldEvent 是客观事件；ObservedEvent 是某个 Agent 的认知版本。两者必须使用不同类型和日志，不能用一个事件对象加“是否可见”字段混合处理。

## 5. Tick 事务模型

每个 time block 建议按以下顺序执行：

1. 从当前 WorldState 创建只读 tick 快照。
2. 执行环境系统变化，例如天气转移和地点开关。
3. 基于同一个快照为每个 Agent 生成 Observation。
4. 每个 Agent 更新主观状态并提出 ActionProposal。
5. 收集全部提案，不立即修改世界。
6. 按固定、可复现规则校验提案。
7. 解决互斥行为和资源冲突。
8. 提交被接受的行为。
9. 生成结构化 WorldEvent 并写入 WorldLog。
10. 把本 tick 的 WorldEvent 分发为各 Agent 的 ObservedEvent。
11. Agent 更新记忆；小说家 Recorder 保存材料。
12. 生成 checkpoint，然后推进到下一个 time block。

这个流程保证 Agent 的决策不会因为遍历顺序而获得不同输入。

## 6. 事件设计原则

### 6.1 结构化事实优先

WorldEvent 至少应明确：

- 事件 ID。
- 运行 ID、day、time block。
- 地点。
- 事件类型。
- 参与者。
- 动作来源。
- 结构化结果。
- 可公开与隐藏字段的边界。
- 因果来源，例如 ActionProposal ID。

面向人的 `summary` 只能是派生描述，不能作为后续规则判断的唯一输入。

### 6.2 事件不等于故事

事件只描述发生了什么。它不负责解释文学意义，也不决定小说家是否注意到它。

### 6.3 来源必须可追踪

应能追踪：

- ActionProposal 到 ActionResult。
- ActionResult 到 WorldEvent。
- WorldEvent 到 ObservedEvent。
- ObservedEvent 到 Experience。
- Experience 或 ObservedEvent 到日记材料。
- 日记与片段到章节。

## 7. 有限感知边界

### 7.1 Observation 最小内容

Observation 可以包含：

- 当前 day、time block、天气。
- Agent 自己当前位置。
- Agent 可知的自身状态。
- 同地点可见人物。
- 当前可感知事件。
- 已听到的传闻。
- 基于环境规则计算出的可用行为。

Observation 不包含：

- 完整 agent_locations。
- 其他地点完整状态。
- 完整 WorldLog。
- 其他 Agent 的内心、需求或私有记忆。
- WorldEvent 的隐藏原因和隐藏 payload。

### 7.2 感知模式

MVP 至少区分：

- `direct`：同地点直接看到或听到，确定性高。
- `participant`：自己参与并收到结果，确定性高。
- `rumor`：由同地点 Agent 的交谈行为传播，确定性较低。
- `unclear`：只获得模糊线索，确定性低。

### 7.3 传闻限制

传闻不能凭空从 WorldLog 跳到小说家 Observation。它必须有传播者、传播行为、来源事件或来源记忆，并保持不确定性。

## 8. Agent 决策边界

### 8.1 候选行为来源

候选行为应从以下内容生成：

- 当前可用行为。
- 时间和天气。
- 习惯触发。
- 客观身体状态的可知部分。
- 个人目标和记忆。
- 同地点人物与关系认知。

### 8.2 行为评分

MVP 使用可解释的规则评分，至少记录：

- 习惯贡献。
- 需求贡献。
- 时间与天气贡献。
- 地点贡献。
- 关系或社交贡献。
- seed 控制的随机扰动。

每次提案都应有可审计的理由，但理由不是客观事实。

### 8.3 LLM 的位置

MVP 中 LLM 不参与世界事实生成。它只可以：

- 把允许的写作材料整理成日记。
- 把日记整理成小说片段。
- 把七天材料整理成章节。

后续如果让 LLM 参与 Agent 决策，它也只能生成 ActionProposal，并继续受 Environment 校验。

## 9. 小说家与普通居民的关系

小说家应复用普通 Agent 的全部行为和感知路径。不能为小说家建立一条直接读取环境的快捷路径。

小说家的额外组件仅包括：

- Recorder。
- Experience 生成规则。
- 日终写作倾向。
- 写作输出触发器。

小说家的“观察能力略高”只能表现为感知规则参数差异，不能表现为读取完整世界。

## 10. 世界独立运行模式

MVP 建议至少定义三种逻辑运行模式，实际 CLI 名称可在实现时决定：

- 世界模式：无小说家、无写作，只验证小镇能独立运行。
- 观察模式：包含小说家和 Recorder，但不生成文学文本。
- 完整模式：世界、小说家记录和写作全部启用。

三种模式应复用同一个 World Runtime。世界模式的存在是验证“世界不是为小说家临时生成”的关键。

## 11. 配置边界

配置负责声明稳定规则和初始数据，不负责保存运行时状态。

配置至少应覆盖：

- 世界和时间设置。
- seed 与随机策略。
- 天气状态与转移规则。
- 地点及连接。
- 地点开放规则。
- Agent 静态资料和初始主观偏好。
- 最小习惯。
- 写作提示约束。

配置加载时必须进行引用完整性检查，禁止不存在地点、Agent 或习惯目标进入运行时。

## 12. 持久化和重放边界

为了证明世界真实运行而不是文本伪造，MVP 应保存：

- 原始配置快照。
- seed。
- 每个 tick 的 WorldEvent。
- 必要 checkpoint。
- 小说家材料来源链。

同一配置和 seed 的重放应产生相同 WorldLog。写作文本可以因为未来真实 LLM 的非确定性不同，但它使用的来源材料必须相同。

## 13. 架构审查问题

每完成一个步骤，都需要回答：

- 这个模块是否读取了它不该知道的数据？
- 这个模块是否修改了它不拥有的数据？
- 是否新增了第二个世界真源？
- 是否让文本生成反向影响了世界？
- 是否能通过固定 seed 重放？
- 是否能说明一个行为为什么被提出、为什么被接受或拒绝？
- 是否能说明一条日记事实来自哪个 ObservedEvent 或 Experience？
