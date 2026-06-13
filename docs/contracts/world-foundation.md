# 世界基础系统契约

状态：Frozen for Step 07-09  
生效日期：2026-06-12

## 1. WeatherSystem

- 天气是客观世界状态，只能由未来 Environment 调用 `advance` 推进。
- 天气在配置指定的 time block 每天最多转移一次。
- 所有转移使用 RunContext 提供的 `DeterministicRandom`。
- 每次推进产生 `WeatherChange`，并保存在天气状态日志中。
- `WeatherEffects` 提供移动、人流、观察和传闻倍率。
- 当前 `WorldSnapshot` 只暴露当前天气，不暴露未来天气或转移概率。

## 2. LocationSystem

- 地点定义和拓扑由配置冻结，LocationSystem 本身不保存 Agent 位置。
- 所有连接必须双向；单向连接视为配置错误。
- 开放规则要么为 `always`，要么明确列出开放 time block。
- `is_public` 表示地点是否公共可访问。
- `is_core_narrative` 表示地点是否属于第一阶段五个核心叙事地点。
- 地点开放状态由统一 WorldClock 的当前 time block 推导。

### 核心叙事地点

- 小说家的家：核心叙事地点，非公共访问。
- 白钟咖啡馆：核心叙事地点，公共访问。
- 小镇图书馆：核心叙事地点，公共访问。
- 中央市场：核心叙事地点，公共访问。
- 旧车站：核心叙事地点，公共访问。

### 私人运行节点

另外五位居民各自拥有一个非公开、非核心叙事住处节点。它们用于起居、移动和日程闭环，不扩大 MVP 的主要叙事场景。

## 3. WorldState

- WorldState 是唯一客观世界真源，由未来 Environment 持有。
- WorldState 持有：
  - WorldClock。
  - WeatherSystem。
  - LocationSystem。
  - Agent 客观位置。
  - Agent 客观身体状态。
  - tick 序号。
- Agent 不保存权威当前位置，也不能获得 WorldState。
- WorldState 的客观修改必须通过明确方法，并在提交前校验。
- 非法修改会抛出 `WorldStateInvariantError`，且不得留下部分修改。

## 4. WorldSnapshot

WorldSnapshot 是从 WorldState 复制出的深度不可变投影：

- 包含当前时间、天气、tick。
- 包含地点状态快照。
- 包含 Agent 客观位置和身体状态快照。
- 不包含推进或修改能力。
- 创建后不会随 WorldState 后续变化而改变。

WorldSnapshot 仍然是完整客观投影，只允许 Environment 和 Perception 使用，不能直接交给 Agent。

## 5. Checkpoint

WorldStateCheckpoint 保存：

- tick。
- ClockSnapshot。
- WeatherSnapshot 与天气变化日志。
- Agent 客观位置。
- Agent 客观身体状态。
- schema version。

WorldState checkpoint 不保存随机数状态。完整恢复必须同时使用 RunContext manifest 中的随机数状态；组合规则见 `runtime-and-agents.md`。
