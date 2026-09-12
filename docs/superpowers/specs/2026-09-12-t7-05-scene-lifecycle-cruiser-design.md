---
schema_version: specification/v1
spec_version: 1.0.0
title: 业务场景五档生命周期自动巡航与金牌样例自学习闭环设计
bet_id: BET-Y1Q4-T7-05
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
---


# T7-05 — Scene Lifecycle Cruiser & Golden Sample Loop 设计

## 1. 问题

场景卡五档生命周期 (`draft → shadow → assisted → supervised → routine`,
见 `.omo/standards/scene-card-lifecycle.yaml`) 目前靠人工判定晋级：

1. **样本门无人计数**：shadow 要求 3-sample、assisted 要求 30-sample +
   calibration ≥ 0.6，但没有组件累计成功执行样本。
2. **校准骤降无熔断**：场景行为漂移（calibration 跌破阈值）时无自动降级，
   可能继续以高档位自动执行。
3. **成功经验不沉淀**：成功履约的旅程没有结构化为可复用的金牌样例，
   同类任务每次从零推理。

## 2. 非目标 (与 ledger non_goals 一致)

- 不绕过 supervised → routine 的高风险人工把关（routine 晋级必须人类确认）。
- 不修改 `value-loop-standard.yaml` 的五阶段状态机定义。
- 不修改任何场景卡 YAML 定义（只读消费）。

## 3. 设计

### 3.1 金牌样例库 (`projects/omo/src/omo/scene/golden_samples.py`)

- `GoldenSample`: dataclass —— `scene_id / input_digest / result_summary /
  calibration / created_at`，digest = sha256(规范 JSON) 防篡改。
- `GoldenSampleStore`: 按 scene_id 索引的内存库 + JSONL 落盘；
  `record()` 去重（同 input_digest 覆盖更新），`find_similar(scene_id,
  top_k)` 按 calibration 降序返回。
- 零模型调用，纯确定性逻辑。

### 3.2 生命周期巡航器 (`projects/omo/src/omo/scene/cruiser.py`)

- `SceneLifecycleCruiser`: 消费 `anchor.py` 的 `ALLOWED_LIFECYCLES` 顺序；
  `observe(scene_id, lifecycle, n_samples, calibration)` 返回决策：
  - `promote`：达到下一档 `min_samples`（shadow:3 / assisted:30）且
    calibration ≥ 0.6（assisted 门）；routine 档只返回 `needs_human`。
  - `demote`：calibration < 0.5 熔断降级并告警（circuit breaker）。
  - `hold`：其余情况维持。
- `CruiseDecision` 携带 machine-readable `code`
  (`promote/shadow-ready/promote/assisted-ready/demote/calibration-drop/
  hold/needs_human`)。

### 3.3 Cockpit 呈递 (`projects/cockpit/src/cockpit/handlers/scene_lifecycle.py`)

- `lifecycle_status(cards)`: 聚合场景卡生命周期分布 + 样本雷达
  （每档计数与晋级缺口），纯函数，可直接被 CLI/handler 调用。
- 不新增 Cockpit 路由；只提供可被现有命令消费的聚合函数。

### 3.4 测试 (`projects/omo/tests/unit/test_scene_lifecycle_cruiser.py`)

覆盖：自动晋级（3-sample→shadow、30+0.6→assisted）、校准不足 hold、
calibration<0.5 熔断降级、routine 需人工、金牌样例去重与检索排序。

## 4. 验收

- `uv run pytest projects/omo/tests/unit/test_scene_lifecycle_cruiser.py -q` exit 0
- `make gac-local-gate` exit 0
