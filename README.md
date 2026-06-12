# Town Diary Simulator

Town Diary Simulator 是一个“世界先独立运行，小说家只记录自身体验”的小镇生活模拟项目。

当前实现状态：完成 Step 00-06，包含冻结契约、Python 项目骨架、核心数据契约、配置校验、确定性运行上下文和 WorldClock。尚未实现天气、地点、Environment、Agent、感知或写作逻辑。

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

当前 CLI 只验证参数和启动边界，不会创建输出目录或执行模拟。

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
- [逐步骤实施清单](docs/03-step-by-step-delivery-checklist.md)
- [验收与来源追踪](docs/04-acceptance-and-traceability.md)

## Development Records

每个 Step 的改动、说明、代码解释和分析记录在 `dev/*.dev.md`。
