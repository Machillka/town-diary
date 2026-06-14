# Town Diary Simulator

Town Diary Simulator 是一个“世界先独立运行，小说家只记录自身体验”的小镇生活模拟项目。

当前实现状态：完成 Step 00-17，包含确定性世界基础、World Runtime、组合 checkpoint、结构化 WorldLog、两阶段 tick、冲突解决，以及六个 Agent 的可解释规则行为。尚未实现完整感知、传闻、小说家记录或写作逻辑。

## Requirements

- Python 3.11+
- uv

## Run

```powershell
uv run town-diary simulate --days 1 --seed 42
```

也可以在安装项目后运行：

```powershell
python -m town_diary simulate --days 1 --seed 42
```

完整的当前参数示例：

```powershell
uv run town-diary simulate `
  --days 7 `
  --seed 42 `
  --config configs `
  --output outputs/run_001 `
  --mode full `
  --llm mock
```

CLI 的 `world` 模式会在没有小说家和写作系统时运行其他居民，并输出天气变化、客观事件数量与运行摘要。`observe` 和 `full` 仍只验证启动边界。

## Test

```powershell
uv run pytest
```

## Output Convention

- 每次运行必须使用独立目录，例如 `outputs/run_001`。
- 运行产物默认不提交到版本控制。
- 后续实现不得静默覆盖已有运行目录。

## Architecture Contracts

- [MVP 范围与术语契约](docs/contracts/mvp-scope.md)
- [架构契约](docs/contracts/architecture-contract.md)
- [核心数据契约](docs/contracts/data-contracts.md)
- [世界基础系统契约](docs/contracts/world-foundation.md)
- [Runtime 与 Agent 基础契约](docs/contracts/runtime-and-agents.md)
- [候选行为与行为提交契约](docs/contracts/actions-and-candidates.md)
- [事件、两阶段 Tick 与规则决策契约](docs/contracts/events-ticks-and-rule-decisions.md)
- [逐步骤实施清单](docs/03-step-by-step-delivery-checklist.md)
- [验收与来源追踪](docs/04-acceptance-and-traceability.md)

## Development Records

每个 Step 的改动、说明、代码解释和分析记录在 `dev/*.dev.md`。
