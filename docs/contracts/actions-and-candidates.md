# 候选行为与行为提交契约

状态：Frozen for Step 13-14  
生效日期：2026-06-14

## 1. 候选行为

- `CandidateAction` 是 Agent 的主观行为选项，不是 ActionProposal，也不是客观事实。
- 候选生成只能读取对应 Agent 的 Observation、Agent 自身静态/主观状态和注入的确定性随机源。
- 候选生成不得读取 WorldState、完整地点拓扑或其他 Agent 私有状态。
- 候选必须受 Observation 的 `available_actions`、`available_location_ids` 和 `visible_agents` 限制。
- 每个候选必须保存可审计评分贡献和行为理由。

最小评分来源包括：

- habit
- need
- weather
- goal
- relationship
- subjective_state
- random

## 2. 最小需求

- 能量恢复需求和饥饿从 Observation 中自己的客观身体状态派生。
- 社交需求从当前有限可见人物派生。
- 小说家写作倾向由普通 Agent 路径根据 role 和时间派生。
- 派生需求不成为第二份客观状态，也不能直接修改 WorldState。

## 3. ActionProposal

- Agent 只能把候选转换为 ActionProposal。
- ActionProposal 表示意图，不表示行为已发生。
- ActionProposal 必须包含确定性生成的 action ID、Agent ID、行为类型和主观理由。
- Agent 不拥有 ActionExecutor 或 WorldState 修改能力。

## 4. Environment 校验与执行

- `ActionValidator` 只读检查提案和当前 WorldState。
- `ActionExecutor` 是唯一行为提交入口。
- 所有失败结果必须给出明确原因，且不得改变 WorldState。
- 成功结果必须是结构化 ActionResult。
- 每个成功结果生成至少一个 WorldEvent，并通过 `source_action_id` 保持来源关系。

### MVP 行为规则

| 行为 | 主要前置条件 | 当前客观效果 |
| --- | --- | --- |
| stay | 不接受目标 | 无 |
| move | 目标存在、相邻、开放且有访问权 | 修改 Agent 客观位置 |
| work | 居民位于开放且当前习惯激活的工作地点 | 降低能量、提高饥饿 |
| rest | 不接受目标 | 恢复能量、提高少量饥饿 |
| observe | Agent 有能量，不接受目标 | 当前无状态修改 |
| talk | 目标 Agent 与提案者同地点 | 降低少量能量、提高少量饥饿 |
| write_notes | 提案者是小说家且有能量 | 当前无状态修改 |

主动行为 move、work、observe、talk 和 write_notes 要求 Agent 能量大于零。
