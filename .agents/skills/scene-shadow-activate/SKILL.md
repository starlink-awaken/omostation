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
# docs/scene-cards/<scene-id>.yaml
schema: scene-card/v2
scene_id: <scene-id>
lifecycle: draft
bet: <BET-ID>
falsifier: "<可证伪条件, validate --all 必填>"
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
python3 bin/ssot/scene-card-lifecycle.py transition \
  --scene-card docs/scene-cards/<scene-id>.yaml --tier shadow --actor <operator>
# draft→shadow 需 approval_state: confirmed (human gate)
```

### Step 3: 积累 trial (2026-09-05 实况, BET-Y2Q1-T7-02)

```bash
# journey-runner 无 --samples 参数; 跑 N 次即 N 个 trial
python3 bin/ssot/journey-runner.py run --journey <journey-id> --dry-run
# 分支演练: --input '{"requires_forwarding": false}'
# 每次完成的 run 自动落盘 shadow-scene-trials.jsonl (mode 字段区分 dry_run/live)
```

### Step 4: 验证 readiness (升级 assisted 的门)

```bash
python3 bin/ssot/scene-card-lifecycle.py check --scene-card docs/scene-cards/<scene-id>.yaml
# trial_recorded=true (按 scene_id 精确匹配) + blockers 空 + approval confirmed → ready
# calibration (review 工具) 是补充视图; assisted 升级门以 readiness 为准
```

### Step 5: shadow → assisted

```bash
python3 bin/ssot/scene-card-lifecycle.py transition \
  --scene-card docs/scene-cards/<scene-id>.yaml --tier assisted --actor <operator>
```

## 相关

- `.omo/standards/scene-card-lifecycle.yaml` — 5 级生命周期
- `bin/ssot/scene-card-lifecycle.py` — 五档 transition/readiness (T7-02 试验门)
- `bin/ssot/scene-card-review.py` — 校准/审查视图 (2026-09-05 起读 docs/scene-cards)
- `docs/superpowers/specs/` — 设计规格库
