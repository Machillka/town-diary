# Town Diary Simulator 实施文档

本目录是基于三份原始 DOCX 整理出的统一项目分析和实施基线。本轮只包含项目与步骤分析，不包含业务代码。

## 推荐阅读顺序

1. `00-project-understanding.md`
   - 统一项目目标、核心因果链、MVP 范围和原文冲突裁决。
2. `01-architecture-boundaries.md`
   - 明确 Environment、Agent、Perception、Recorder 和 Writing 的边界与数据所有权。
3. `02-implementation-roadmap.md`
   - 查看里程碑、关键路径、依赖关系和退出门槛。
4. `03-step-by-step-delivery-checklist.md`
   - 按 35 个小步骤逐项实施、交付和验收。
5. `04-acceptance-and-traceability.md`
   - 执行世界独立、有限感知、传闻、文本泄漏、重放和来源链验收。
6. `next-actions.md`
   - 查看实际开工时的首轮顺序和标准执行循环。

每个已实施 Step 的改动、代码解释、分析和验证结果记录在 `../dev/*.dev.md`。

## 一句话架构判断

世界先独立运行；所有居民基于有限感知提出行为；Environment 提交客观事实；小说家只是记录自己体验的 Agent camera；写作只能消费小说家的可知材料。

## 开工规则

- 每次只执行 `03-step-by-step-delivery-checklist.md` 中的一个 Step。
- 当前 Step 的退出门槛未满足前，不进入下一步。
- 每次修改后检查 `04-acceptance-and-traceability.md` 中的 P0 边界。
- 长期执行过程中持续更新 `next-actions.md` 和 devlog。
