---
name: scene-shadow-activate
description: "场景影子激活 skill：将 scene card 从 draft/shadow 阶段推进到 assisted/supervised 生命周期"
title: Scene Shadow Activate
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - new scene card
  - scene promotion request
  - Y1 scenario activation
---

# scene-shadow-activate — 场景卡 Shadow 模式激活

> 将 docs/operations/scene-activation-playbook.md Shadow 模式 4 步转为可执行 skill

## 前提

- 场景卡 YAML 必须有 17 个必填字段
- journey_id 必须指向有效 journey spec

## 执行步骤

### Step 1: 创建场景卡 (draft)

```yaml
# .omo/_truth/scenarios/<scene-id>.yaml
schema: scene-card/v1
scene_id: <scene-id>
lifecycle: draft
journey_id: <journey-id>
goal: <one-line-goal>
trigger: <trigger-condition>
input_contract: <input-schema>
result_contract: <output-schema>
outcome_metric: <metric>
owner: <owner>
failure_cost: low/medium/high
data_classification: internal/public
data_scope: <scope>
operator: omo-resident
permission_ref: bos://resident/...
rollback_plan: <rollback>
```

### Step 2: 升级到 shadow

```bash
python3 bin/ssot/scene-card-review.py promote <scene-id> --to shadow
```

### Step 3: 积累 3 个 sample

```bash
python3 bin/ssot/journey-runner.py run <journey-id> --dry-run --samples 3
```

### Step 4: 验证 calibration

```bash
python3 bin/ssot/scene-card-review.py validate <scene-id>
# calibration >= 0.6 才能升级到 assisted
```

## 相关

- `.omo/standards/scene-card-lifecycle.yaml` — 5 级生命周期
- `bin/ssot/scene-card-review.py` — 场景卡审查工具
- `docs/superpowers/specs/` — 设计规格库
