# Project Contracts

本目录保存 MVP-0.1 实现期间必须遵守的冻结契约。

- `mvp-scope.md`：范围、术语和产品决策。
- `architecture-contract.md`：数据所有权、依赖方向、禁止访问和运行模式。
- `data-contracts.md`：核心字段、ID、可见性和配置 schema 说明。
- `world-foundation.md`：天气、地点、WorldState、快照和 checkpoint 契约。
- `runtime-and-agents.md`：World Runtime、组合 checkpoint、重放和 Agent 主观状态契约。

当实现与分析文档存在歧义时，先遵守本目录中的冻结契约；如需修改契约，必须在对应 `dev/*.dev.md` 中记录原因和影响。
