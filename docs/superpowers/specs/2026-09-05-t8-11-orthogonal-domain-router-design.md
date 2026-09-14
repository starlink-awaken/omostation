---
schema_version: specification/v1
spec_version: 1.0.0
title: Orthogonal domain tree and dual-track transparent router
bet_id: BET-Y1Q4-T8-11
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-05
last-reviewed: 2026-09-05
type: ssot
last_updated: 2026-09-05
---

# Orthogonal domain tree and dual-track transparent router (T8-11)

## Intent

建立 `ORTHOGONAL_DOMAINS` 8 大正交一级领域树，并通过双轨透明预处理路由器保持存量无前缀命令 100% 兼容。交付已在 Project Sovereign Command (PSC v1) 合入；本 Spec 作为 closeout 的 canonical SpecificationBinding。

## Architecture

```
projects/cockpit/src/cockpit/_subcommands.py
├─ ORTHOGONAL_DOMAINS: 8 域一级树
├─ 双轨预处理：cockpit <cmd> ↔ cockpit <domain> <cmd>
└─ 领域 help：富文本功能地图 + 双轨调用提示

projects/cockpit/tests/test_command_hierarchy.py
└─ 覆盖领域定义、别名分发与帮助提示
```

## Acceptance

- 8 大正交领域树在 help 中清晰展现
- 双轨路由器透明拦截并映射旧命令
- `PYTHONPATH=projects/cockpit/src python3 -m pytest -q projects/cockpit/tests/test_command_hierarchy.py` 全绿

## Non-goals

- 不破坏存量无前缀命令调用
- 本 closeout 不 bump `projects/cockpit` gitlink（交付已在 main 可达）
