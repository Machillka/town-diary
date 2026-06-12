# MVP-0.1 范围与术语契约

状态：Frozen for Step 01  
生效日期：2026-06-12

## 1. 核心目标

MVP-0.1 必须证明：

1. 小镇世界可以在没有小说家和写作模块时独立推进。
2. 所有居民基于有限感知和自身状态提出行为。
3. Environment 校验并提交行为，形成客观事件。
4. 小说家只记录自己实际感知和体验到的内容。
5. 写作系统只使用小说家的可知材料。
6. 七天材料可以整理成第一章草稿。

## 2. 冻结术语

| 术语 | 唯一含义 |
| --- | --- |
| Environment | 客观世界的唯一修改入口和生命周期控制者 |
| WorldState | Environment 独占持有的完整客观世界状态 |
| WorldSnapshot | 从 WorldState 生成的只读时点投影 |
| Agent | 基于 Observation 和自身主观状态提出 ActionProposal 的居民 |
| Observation | 某个 Agent 在当前 tick 可感知的世界切片，也是决策的唯一世界输入 |
| ActionProposal | Agent 提出的行为意图，不代表行为已经发生 |
| ActionResult | Environment 对行为提案校验与提交后的结果 |
| WorldEvent | 已经客观发生的结构化世界事件 |
| ObservedEvent | 某个 Agent 对 WorldEvent 的主观认知版本 |
| Experience | 小说家基于已知材料形成的感受、解释或推测 |
| Recorder | 只记录小说家实际收到的 Observation、ObservedEvent 和 Experience 的组件 |
| Writing | 只读小说家材料并生成文本的下游组件 |

## 3. MVP-0.1 必须包含

- 七天、每天五个 time block 的世界推进。
- 晴、阴、小雨、大雨的最小天气系统。
- 五个公开叙事地点和居民私人住处节点。
- 小说家与五位居民。
- 最小需求、习惯和规则决策。
- ActionProposal、校验、冲突解决和提交。
- 结构化 WorldEvent 与 WorldLog。
- 有限 Observation、直接观察和最小传闻。
- 小说家 ObservationLog 与规则化 ExperienceLog。
- MockLLM 下的日记、小说片段和章节。
- 固定 seed 重放、checkpoint 恢复和来源追踪。

## 4. MVP-0.1 明确延期

- 真实 LLM API 作为必需依赖。
- Web UI、游戏引擎或完整 galgame UI。
- 大规模居民、复杂经济、战斗和剧情导演。
- 动态习惯学习。
- 多跳传闻、复杂失真和长期遗忘。
- 向量数据库、复杂 RAG 和反思记忆。
- 多线程或分布式模拟。
- 长篇小说自动生成。

## 5. 私人住处决策

MVP 使用“最小非公开地点节点”表示居民私人住处。

- 私人住处参与地点连接、移动、日程和状态校验。
- 私人住处不是公开叙事地点，不要求成为小说家的常规访问目标。
- 所有 Agent 的 `home_location_id` 必须引用真实存在的地点节点。
- 不使用工作地点代替住处，不使用无地点语义的全局 offstage 状态。

## 6. 三层信息边界

### 客观事实

只存在于 WorldState、ActionResult 和 WorldEvent 中，由 Environment 管理。

### 主观认知

只存在于 Observation、ObservedEvent、Agent Memory 和 Experience 中，允许不完整或错误。

### 文本表达

日记、小说片段和章节只能从小说家主观认知材料生成，不能新增客观事实。

## 7. 范围判断规则

一个需求只有在直接帮助证明六项核心目标时，才属于 MVP-0.1。仅改善视觉效果、文学质量、规模或未来扩展性的需求，默认延期。
