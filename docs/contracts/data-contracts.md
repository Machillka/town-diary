# MVP-0.1 核心数据契约

状态：Frozen for Step 04  
schema version：`0.1`

代码定义位于 `src/town_diary/core/contracts.py`。本文档解释字段语义和信息边界。

## ID 约定

### 配置静态 ID

Agent 与 Location 等配置 ID 使用小写 snake case，例如：

- `novelist`
- `cafe_owner`
- `novelist_home`

### 运行生成 ID

运行中生成的 ID 使用类型前缀和六位顺序号：

- `action_000001`
- `event_000001`
- `experience_000001`

Run ID 使用 `run_` 前缀，默认由 seed 和配置摘要生成。

## 公共枚举

- `TimeBlock`：`morning`、`noon`、`afternoon`、`evening`、`night`。
- `Weather`：`clear`、`cloudy`、`light_rain`、`heavy_rain`。
- `PerceptionMode`：`direct`、`participant`、`rumor`、`unclear`。
- `FactVisibility`：`public`、`participant`、`hidden`。

## `WorldSnapshot`

完整客观世界的只读时点投影，仅允许 Environment 和 Perception 使用。

| 字段 | 含义 |
| --- | --- |
| `day` | 当前世界日 |
| `time_block` | 当前统一时间段 |
| `weather` | 当前客观天气 |
| `tick` | 当前已提交 tick 序号 |
| `location_states` | 地点开放、公共访问和核心叙事标记的只读投影 |
| `agent_states` | Agent 客观位置与身体状态的只读投影 |
| `schema_version` | 快照 schema 版本 |

Agent 不能直接读取 `WorldSnapshot`。

## `Observation`

某个 Agent 当前可感知的世界切片，也是 Agent 决策的唯一客观世界输入。

| 字段 | 含义 |
| --- | --- |
| `observer_id` | 观察者 |
| `day`、`time_block` | 观察者可知的当前时间 |
| `location_id` | 观察者可知的自身位置 |
| `weather` | 当前可感知天气 |
| `body_state` | 观察者可知的自身客观身体状态 |
| `visible_agents` | 同地点或规则允许看见的 Agent |
| `visible_events` | 可直接观察或参与的事件版本 |
| `heard_rumors` | 通过传播行为获得的低确定性事件版本 |
| `available_actions` | Environment 当前允许提议的行为类型 |

## `ActionProposal`

Agent 的行为意图，不表示行为已经发生。

| 字段 | 含义 |
| --- | --- |
| `action_id` | 可追踪的行为提案 ID |
| `agent_id` | 提案者 |
| `action_type` | 行为类型 |
| `reason` | Agent 的主观决策理由 |
| `target_location_id` | 可选目标地点 |
| `target_agent_id` | 可选目标 Agent |
| `parameters` | 额外结构化提案参数 |

## `ActionResult`

Environment 校验与提交 ActionProposal 后的结果。

| 字段 | 含义 |
| --- | --- |
| `action_id` | 对应提案 ID |
| `success` | 行为是否被提交 |
| `reason` | 接受或拒绝原因 |
| `events` | 成功提交后产生的客观事件 |

失败结果不得改变 WorldState，也不得产生伪装为成功的 WorldEvent。

## `WorldEvent`

已经客观发生的结构化世界事实。

| 字段 | 含义 |
| --- | --- |
| `event_id` | 客观事件 ID |
| `day`、`time_block` | 发生时间 |
| `location_id` | 发生地点 |
| `event_type` | 可供规则判断的事件类型 |
| `participants` | 客观参与者 |
| `summary` | 面向人的可读摘要，不是唯一事实来源 |
| `facts` | 带可见性边界的结构化事实 |
| `source_action_id` | 可选来源提案 |

`facts.visibility` 决定事实可否进入 ObservedEvent。隐藏事实不得被 Perception 暴露。

## `ObservedEvent`

某个 Agent 对一个 WorldEvent 的有限认知版本。

| 字段 | 含义 |
| --- | --- |
| `source_event_id` | 来源客观事件 |
| `observer_id` | 当前认知者 |
| `day`、`time_block` | 获得认知的时间 |
| `description` | 认知者可理解的描述 |
| `mode` | 直接观察、参与、传闻或模糊线索 |
| `certainty` | 主观确定性 |
| `perceived_facts` | 已经过滤的结构化事实 |

## `Experience`

小说家基于已知材料形成的主观感受、解释或推测。

| 字段 | 含义 |
| --- | --- |
| `experience_id` | 体验 ID |
| `day`、`time_block` | 体验形成时间 |
| `source_event_ids` | 已知来源事件 |
| `feeling` | 主观感受 |
| `interpretation` | 主观解释或推测 |
| `certainty` | 对解释的主观确定性 |

Experience 不能成为新的客观事实。

## 配置文档

Step 04 要求 `world.yaml`、`locations.yaml`、`agents.yaml` 使用相同且受支持的 `schema_version`。

配置加载会拒绝：

- 缺失必需文档或字段。
- 不受支持或不一致的 schema version。
- 不稳定 ID 和重复 ID。
- 不存在地点的连接、住处和初始位置引用。
- 非法天气枚举。
- 非法 Agent role。
- 不是恰好一个小说家的 Agent 集合。
