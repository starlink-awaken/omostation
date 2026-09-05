---
id: ADR-0412
title: "model-driven (M0) 定位判定 — 接入主链 (保留独立子仓)"
status: archived
lifecycle: spec
owner: governance-team
created: 2026-08-16
last-reviewed: 2026-08-16
related:
  - ./0399-blueprint-consolidation.md
  - ../../../docs/plans/3y-bet-ledger.yaml#BET-Y1Q2-T1-02
type: ssot
---

# ADR-0412: model-driven (M0) 定位判定 — 接入主链 (保留独立子仓)

## 判定

**接入主链，保留独立子仓，不降库不归档。**

## 实测证据 (2026-08-16, 判定依据=调用链非设计意图)

| 证据 | 实测 | 指向 |
|---|---|---|
| 跨仓 python import | 仅 1 处: cockpit 防腐适配器 `adapters/model_driven.py` (8 符号: Pipeline/Transition/OKR/Spec/DerivationEngine/mof_scan/tools) | 真实代码消费 |
| cockpit CLI 入口 | `cockpit model-driven` 命令经 l4bridge 实调适配器 (l4bridge.py:341) | 用户可达 |
| MOF 主链 | m2-ssot-inventory 扫描其 51 个 .py; check-mof-capabilities-drift 引用 mcp_server.py | 治理面依赖 |
| CI 平面 | ci-python-coverage path-filter + audit-rollout-monthly --repos | 构建面依赖 |
| ecos-link | bin/mof/ecos-link 映射注册 | 工具链接入 |

## 三案对比

- **接入主链 ✅**: 有真实消费 (cockpit 适配器) + 治理/CI 双面依赖; M0 生命周期管理是 MOF m3 扩展的活组件
- **降库 (ecos 内包) ❌**: cockpit 是唯一代码消费者, 但 MOF 治理工具直接扫子仓目录 — 内包将破坏 m2-ssot-inventory 的独立扫描语义
- **归档 ❌**: 8 个被 import 的符号含 DerivationEngine/mof_scan 等 MOF 活组件, 非死代码

## 后果

- BET-Y1Q2-T1-01 (omo-debt+c2g 归并) **不涉及** model-driven — 三仓归并范围不变
- M0 保持 submodule; 后续若 cockpit 适配器符号消费归零可重开判定
