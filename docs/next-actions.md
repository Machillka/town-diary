# Next Actions

## 当前状态

2026-06-13 已完成：

- Step 00：完成三份 DOCX 的统一项目分析和实施基线。
- Step 01：冻结 MVP 范围、术语和私人住处节点方案。
- Step 02：冻结数据所有权、禁止访问、两阶段 tick 和运行模式。
- Step 03：建立 Python 项目骨架、最小 CLI、测试入口和输出约定。
- Step 04：建立核心数据契约、schema version 和配置校验。
- Step 05：建立确定性随机数、运行生成 ID 和 RunContext。
- Step 06：实现五时间段 WorldClock 与快照恢复。
- Step 07：实现确定性 WeatherSystem、天气效果与状态日志。
- Step 08：实现正式地点拓扑、开放规则与私人住处节点。
- Step 09：实现 WorldState、深度不可变快照、状态不变量与 checkpoint。
- Step 10：实现 World Runtime 生命周期与独立 world 模式。
- Step 11：实现组合 checkpoint、恢复与基础重放。
- Step 12：实现六个 Agent 的静态资料和私有主观状态。
- 建立 `dev/*.dev.md` 记录规则，并持续记录 Step 00-12 的改动、解释、分析和验证。

当前代码包含确定性世界基础、World Runtime、组合 checkpoint、基础重放和 Agent 主观状态；尚未实现候选行为、行为提交、感知、完整事件日志或写作逻辑。

## 首轮执行顺序

下一轮按以下顺序执行，不要一次实现多个步骤：

1. 执行 Step 13，实现最小需求、习惯触发和候选行为生成。
2. 执行 Step 14，实现 ActionValidator 与 ActionExecutor。
3. 执行 Step 15，实现结构化 WorldEvent 与 WorldLog。

## 每个步骤的标准执行循环

1. 阅读 `03-step-by-step-delivery-checklist.md` 中当前步骤。
2. 确认所有前置条件已满足。
3. 只实现当前步骤的范围。
4. 添加或更新当前步骤需要的测试。
5. 运行对应测试和必要的完整回归。
6. 对照当前步骤的交付清单逐项检查。
7. 对照 `04-acceptance-and-traceability.md` 检查是否破坏 P0 边界。
8. 更新 devlog 和本文件。
9. 当前步骤退出门槛全部满足后，才开始下一步。

## 已冻结产品决策

居民私人住处采用最小非公开地点节点。所有 `home_location_id` 必须引用真实节点，不使用工作地点替代住处，也不使用全局 offstage 状态。

## 第一阶段严禁提前加入

- 真实 LLM API。
- Web UI 或游戏引擎。
- 向量数据库。
- 复杂剧情导演。
- 多线程模拟。
- 大规模 Agent。
- 复杂关系和复杂记忆。
- 任何 Writer 读取 WorldLog 的快捷实现。
