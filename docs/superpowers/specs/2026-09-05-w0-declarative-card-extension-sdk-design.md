---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-09-05
last-reviewed: 2026-09-05
bet_id: BET-Y1Q4-T8-20
risk_level: L1
human_gate: false
value_indicator_policy: false
implementation_authorized: true
---

# W0 Declarative Card Extension SDK & Plug-and-Play Surface Manifest Design

## 1. Decision & Background

Following the establishment of Unified Surface Protocol (USP v1, BET-Y1Q4-T8-17), Sovereign TUI 2.0 (BET-Y1Q4-T8-18), and Cockpit-UI 8-Domain Restructuring (BET-Y1Q4-T8-19), all presentation layers render state through standardized `SurfaceEnvelope` and 5 universal card primitives (`MetricGrid`, `DataTable`, `LogStream`, `DagGraph`, `ActionPanel`).

However, to date, rendering cards for custom business domains (such as `family-hub`, `weijian-governance`, `omlxc`) required editing Cockpit internal Python code or TypeScript routes. This violates open-closed architecture and creates tight coupling between external domain applications and the central cockpit kernel.

This specification formalizes the **Declarative Card Extension SDK (DCE SDK v1)** and the `surface.manifest.yaml` contract. Any internal or external subproject declares its user-facing cards and actions purely through declarative YAML, enabling CLI, TUI, and Web UI to auto-discover, validate, and hot-mount domain extensions at runtime.

## 2. Goal and Non-Goals

- **Goal:**
  - Define the `surface-manifest/v1` specification schema for declarative card definitions.
  - Implement a fail-safe, high-resilience manifest scanner and loader in `cockpit.surface.loader`.
  - Automatically map declarative manifest cards into USP v1 `SurfaceEnvelope` instances.
  - Support static data embeds, BOS URI data source references, and parameterized actions.
  - Integrate declarative loading into Sovereign TUI 2.0 (`cockpit.tui.app`), seamlessly appending extension cards into domain CardDecks.
  - Provide a production-ready manifest in `projects/family-hub/surface.manifest.yaml`.
  - Guarantee 100% test coverage for schema parsing, failure isolation, workspace scanning, and card conversion.

- **Non-Goals:**
  - Does not allow executing arbitrary unsafe external binary plugins (actions execute via defined BOS URI transports or safe CLI dispatchers).
  - Does not alter core USP v1 card primitives or serialization schemas.

## 3. Manifest Contract (`surface.manifest.yaml`)

Each extension defines a `surface.manifest.yaml` in its project root:

```yaml
schema_version: surface-manifest/v1
extension_id: family-hub
domain: user
title: "Family Hub 家庭智能中枢"
description: "家庭数字资产管理、健康档案与成员协同"
refresh_interval_ms: 10000
cards:
  - id: family-hub-kpi
    type: metric_grid
    title: "家庭空间运行状态"
    metrics:
      - label: "家庭成员在线"
        value: "4 / 4"
        status: "normal"
      - label: "关键资产健康度"
        value: "98%"
        status: "normal"
      - label: "待审看护事项"
        value: "2 项"
        status: "warning"
  - id: family-hub-tasks
    type: data_table
    title: "家庭重要事项清单"
    columns:
      - key: task
        label: "事项名称"
      - key: member
        label: "关联成员"
      - key: priority
        label: "优先级"
      - key: status
        label: "处理状态"
    rows:
      - task: "医疗保险年度复核"
        member: "长辈"
        priority: "high"
        status: "待签署"
      - task: "分布式备份介质巡检"
        member: "全员"
        priority: "medium"
        status: "已完成"
  - id: family-hub-actions
    type: action_panel
    title: "核心协同操作"
    actions:
      - id: trigger-sync
        label: "立即同步家庭知识库"
        command: "bos://service/family-hub/sync"
        variant: "primary"
      - id: export-brief
        label: "导出家庭晨报"
        command: "bos://service/family-hub/export-brief"
        variant: "secondary"
```

## 4. Architecture & Component Interaction

```
+-------------------------------------------------------------+
| Subproject (e.g. projects/family-hub/surface.manifest.yaml) |
+-------------------------------------------------------------+
                              |
                     [Auto-Discovery / Scan]
                              v
+-------------------------------------------------------------+
|             cockpit.surface.loader.ManifestScanner          |
|    - Schema Validation & Fail-Closed Circuit Breaker        |
|    - Manifest -> USP v1 SurfaceEnvelope Transformation      |
+-------------------------------------------------------------+
                              |
                 [Register into ExtensionRegistry]
                              v
+-------------------------------------------------------------+
|                  Sovereign TUI 2.0 / Web UI                 |
|    - Domain CardDeck automatically renders extension cards  |
|    - Keyboard navigation & action dispatch fully compatible |
+-------------------------------------------------------------+
```

## 5. Verification & Acceptance Criteria

- Unit & integration tests in `projects/cockpit/tests/test_surface_manifest.py` verifying:
  - Valid manifest parsing across supported card types (`metric_grid`, `data_table`, `action_panel`, `log_stream`).
  - Strict validation error handling (missing fields, unknown card types, malformed YAML).
  - Workspace directory traversal and manifest discovery.
  - Safe conversion to USP v1 `SurfaceEnvelope` and rendering in `CardDeck`.
- `projects/family-hub/surface.manifest.yaml` validated against schema.
- Pytest test execution exits with code 0.
