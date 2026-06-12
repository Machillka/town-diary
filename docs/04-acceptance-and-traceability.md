# 验收与来源追踪

## 1. 验收目标

本项目的核心风险不是“程序能不能跑”，而是程序运行后是否仍然遵守世界独立、有限感知、客观行为和文本来源约束。

因此，验收必须同时检查：

- 客观世界是否成立。
- Agent 行为是否有来源并由环境提交。
- 小说家是否只知道自己能够知道的内容。
- 文本是否只使用小说家材料。
- 运行是否可复现、可追踪、可恢复。

## 2. 验收优先级

### P0：不通过则 MVP 失败

- Environment 不是唯一世界真源。
- Agent 可以直接修改世界。
- Agent 或小说家可以读取完整 WorldState。
- Writing 可以读取 WorldLog。
- 未感知事件进入小说家文本。
- 传闻被写成确定事实。
- 世界不能在没有小说家时运行。
- 同一 seed 无法重放相同客观结果。

### P1：应在 MVP 发布前通过

- checkpoint 恢复一致。
- Agent 遍历顺序不污染同 tick Observation。
- 配置引用完整性检查。
- 每条文本材料有来源。
- 输出结构完整。

### P2：可以作为质量改进

- 行为分布更自然。
- 日记与片段文学质量更高。
- 关系和记忆变化更细腻。

## 3. P0 端到端验收场景

### 场景 A：世界在没有小说家时继续运行

### 设置

- 不创建小说家 Agent。
- 禁用 Recorder 和全部 Writer。
- 运行七天。

### 期望

- 时间推进三十五个 tick。
- 天气按规则变化。
- 其他居民继续行动。
- WorldLog 持续产生客观事件。
- 不生成小说家 ObservationLog、ExperienceLog、日记、片段或章节。

### 失败含义

如果世界无法运行，说明 Environment 仍然依赖小说家或写作流程，不是真正独立存在。

---

### 场景 B：小说家错过异地事件

### 设置

- 下午市场发生争执。
- 小说家位于图书馆。
- 没有任何居民向小说家传播此事。

### 期望

- WorldLog 包含市场争执。
- 市场在场者的 ObservedEvent 包含争执。
- 小说家 ObservationLog 不包含争执。
- 小说家 ExperienceLog 不包含争执。
- 当日日记和小说片段不包含争执。
- 七天章节不包含争执。

### 失败含义

任何小说家材料出现争执，都表示 WorldLog 泄漏或 Perception 边界失效。

---

### 场景 C：小说家只听到传闻

### 设置

- 市场发生争执。
- 小说家位于咖啡馆。
- 一位知道争执的居民与小说家交谈，并传播“市场似乎吵起来了”。
- 小说家不知道完整原因。

### 期望

- WorldLog 保存完整客观争执。
- 交谈和传播行为有客观事件。
- 小说家 ObservedEvent 标记为 rumor。
- rumor 保存传播者、来源事件和低确定性。
- 日记可以写“听说市场似乎发生争执”。
- 日记和章节不能补充完整原因。

### 失败含义

如果传闻没有传播行为或补充了完整真相，说明传闻机制实际是全知信息通道。

---

### 场景 D：小说家直接观察事件

### 设置

- 小说家与市场摊主位于市场。
- 市场摊主与学生发生短暂争执。

### 期望

- WorldLog 包含争执。
- 小说家的 ObservedEvent 标记为 direct。
- 小说家知道现场可见事实，但不知道其他人的隐藏动机。
- 日记可以描述亲眼看到的争执。
- 文本不能断言隐藏动机，除非后续通过交谈得知。

### 失败含义

如果小说家无法记录直接观察，感知系统过度过滤；如果知道隐藏动机，则过滤不足。

---

### 场景 E：非法行为不改变世界

### 设置

分别让 Agent 尝试：

- 移动到不相邻地点。
- 夜晚进入关闭的图书馆。
- 与不同地点的 Agent 交谈。
- 提交未知行为类型。

### 期望

- ActionResult 明确失败。
- WorldState 不改变。
- 不产生成功 WorldEvent。
- 可以产生失败审计记录，但不能伪装成已发生行为。

### 失败含义

如果失败行为仍改变世界，Environment 不是可靠的提交边界。

---

### 场景 F：Agent 遍历顺序不污染 Observation

### 设置

- 使用相同世界快照、配置和 seed。
- 分别以不同 Agent 遍历顺序执行同一个 tick。

### 期望

- 每个 Agent 获得的决策 Observation 相同。
- 提案收集阶段 WorldState 不变化。
- 冲突解决后结果遵守同一确定性规则。

### 失败含义

如果结果依赖遍历顺序，说明 tick 不是两阶段事务，后执行 Agent 获得了额外信息。

---

### 场景 G：写作层无法获得 WorldLog

### 设置

- 构造包含一个小说家未知事件的 WorldLog。
- DayWritingMaterials 不包含该事件。
- 执行 DiaryWriter、NovelFragmentWriter 和 ChapterWriter。

### 期望

- Writer 输入中不存在完整 WorldLog。
- 三类文本都不出现未知事件。
- 来源清单中不存在该事件。

### 失败含义

如果未知事件进入文本，说明 Writing 边界失效。

---

### 场景 H：世界结果可重放

### 设置

- 使用固定配置、固定版本和固定 seed 运行七天两次。

### 期望

- 两次运行的客观 WorldLog 一致。
- WorldState 日终快照一致。
- 小说家的 ObservationLog 和 ExperienceLog 一致。
- MockLLM 模式下文本输出一致。

### 失败含义

如果客观结果不一致，说明存在未受控随机源、非确定顺序或隐藏外部依赖。

## 4. P1 验收场景

### 场景 I：checkpoint 恢复一致

### 设置

- 连续运行七天，保存基准结果。
- 第二次运行到第三天日终停止，从 checkpoint 恢复后继续到第七天。

### 期望

- 恢复运行与连续运行的后续 WorldLog 一致。
- 时钟、天气、Agent 客观状态和随机数状态一致。
- 输出不会重复或遗漏。

---

### 场景 J：配置引用完整

### 设置

分别引入：

- 不存在的地点引用。
- 重复 Agent ID。
- 不存在的习惯目标。
- 非法天气状态。
- 无法闭合的开放时间规则。

### 期望

- 在运行前明确失败。
- 错误指出具体配置位置和原因。
- 不进入部分初始化状态。

---

### 场景 K：来源链完整

### 设置

- 从章节中选取一个事实或场景。

### 期望

- 可以追踪到具体日记或小说片段。
- 可以继续追踪到 DayWritingMaterials。
- 可以继续追踪到 Experience 或 ObservedEvent。
- 可以继续追踪到原始 WorldEvent 或小说家主观解释来源。

### 失败含义

无法追踪的文本事实应视为潜在幻觉或越权信息。

## 5. 来源追踪模型

### 5.1 客观行为链

每个已发生的 Agent 行为应能追踪：

`Observation + Agent 主观状态 -> ActionProposal -> 校验与冲突解决 -> ActionResult -> WorldEvent`

### 5.2 主观认知链

每个 Agent 认知应能追踪：

`WorldEvent + 感知规则/传播行为 -> ObservedEvent -> Agent Memory`

### 5.3 小说家体验链

每条 Experience 应能追踪：

`Observation/ObservedEvent + 小说家主观状态 -> Experience`

### 5.4 文本链

每个文本产物应能追踪：

- 日记：`DayWritingMaterials -> diary`
- 小说片段：`diary + key scene -> novel fragment`
- 章节：`7 days diaries + fragments -> chapter`

### 5.5 来源清单最低要求

来源清单至少记录：

- 产物类型和产物 ID。
- 使用的 day 和 time block。
- 使用的 Observation、ObservedEvent、Experience 或上游文本 ID。
- 来源模式，例如 direct、participant、rumor、interpretation。
- 来源确定性。
- 生成器类型和版本。

## 6. 需求追踪矩阵

| 核心需求 | 主要实施步骤 | 主要验收场景 |
| --- | --- | --- |
| 环境独立运行 | Step 09-11、Step 32 | A、H、I |
| 时间与天气推进 | Step 06-07 | A、H |
| Agent 客观行为 | Step 13-18 | E、F、H |
| Environment 唯一真源 | Step 02、09、14-16 | E、F |
| 有限感知 | Step 19-22 | B、C、D、G |
| 小说家是 camera | Step 23-26 | B、C、D、K |
| 日记只来自体验 | Step 26-28 | B、C、G、K |
| 小说片段不改事实 | Step 29 | G、K |
| 章节不补充真相 | Step 30 | B、C、G、K |
| 七天闭环 | Step 32-35 | A、H、I、K |

## 7. 每步通用审查清单

每个步骤完成后都执行：

- [ ] 本步骤是否只修改当前范围？
- [ ] 是否新增了越权读取？
- [ ] 是否新增了第二个世界真源？
- [ ] 是否新增了未受控随机数？
- [ ] 是否新增了无法追踪的自然语言事实？
- [ ] 是否有对应单元或集成验证？
- [ ] 是否运行了相关测试？
- [ ] 是否更新了必要文档和 next-actions？

## 8. MVP 最终交付清单

### 架构

- [ ] Environment 是唯一世界真源。
- [ ] Agent 只基于 Observation 决策。
- [ ] 所有 Agent 行为通过 ActionProposal 提交。
- [ ] WorldEvent 与 ObservedEvent 分离。
- [ ] Writing 不读取 WorldLog，不修改世界。

### 功能

- [ ] 世界可独立运行七天。
- [ ] 时间、天气、地点状态正常推进。
- [ ] 六个 Agent 进行可解释的客观行为。
- [ ] 小说家可以观察、错过、听闻和误解。
- [ ] 每天生成 ObservationLog、ExperienceLog、日记和片段。
- [ ] 七天后生成章节草稿。

### 质量

- [ ] P0 验收场景全部通过。
- [ ] P1 验收场景全部通过。
- [ ] 固定 seed 可重放。
- [ ] checkpoint 可恢复。
- [ ] 文本来源链完整。
- [ ] 无真实 LLM 和无网络时仍可完成 MVP 流程。
