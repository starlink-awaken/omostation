---
title: "runbook-scenario-failure"
type: runbook
owner: governance-team
lifecycle: history
last_updated: 2026-08-23
---
# Runbook: 场景执行失败

## 症状
- Journey 执行 status != succeeded
- 场景产出率为 0

## 排查
```bash
# 场景状态
python3 -c "from ecos.observability.scenario_metrics import scenario_summary; print(scenario_summary())"
# Journey 执行
cd projects/ecos
python3 -c "from ecos.l1.runtime.journey_runner import JourneyRunner; r=JourneyRunner(); print(r.execute_journey('intent-to-execution'))"
```

## 前置检查
- scene-card status 必须为 pilot/active
- journey-spec 必须有 steps/states
