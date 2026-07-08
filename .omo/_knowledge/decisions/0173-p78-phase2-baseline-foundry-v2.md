---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-08
related:
  - 0172-p78-port-registry-convergence.md
  - 0160-p76-phase6-foundry-runtime.md
  - ../../../../../.omo/state/health.yaml
  - ../../../../../bin/decks/port-governance-deck.py
  - ../../../../../docs/operations/knowledge-foundry-monitor.md
supersedes: []
---

# ADR-0173: P78 Phase 2 — 基线重放 + Foundry v2

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-08), P78 Phase 2 收口.

## 0. TL;DR

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **bin/config 端口对齐** | ✅ | 0 unregistered, 0 violations — bin/ 已通过 Phase 7 迁移 |
| **GaC 健康基线 95** | ✅ | `.omo/state/health.yaml`: governance 100, planned tasks 0 |
| **Foundry v2: port-governance deck** | ✅ | `bin/decks/port-governance-deck.py` (4 checks + catalog metrics) |
| **gac-local-gate** | ✅ | 29/30 PASS (cc-switch pre-existing) |
| **catalog 60 原则** | ✅ | 55 + 5 新基线原则 (P79-1..5) |

## 1. Tem 1: bin/config 端口 SSOT 对齐

所有 `bin/` 和 `config/` 端口引用已验证与 port-registry 一致:
- `bin/start-gateway.sh`: 1234 (LM Studio LEGACY, 豁免) + 9290 (已迁移 → `LLM_GATEWAY_PORT`)
- `bin/gac-mesh-router.py`: 7437 (已迁移 → `OMLX_MESH_ROUTER_PORT`)
- 其他 bin/ 文件无未注册端口
- config/ 目录不存在 (未使用)

## 2. Task 2: GaC 健康基线重放

| 指标 | 当前值 | 趋势 |
|------|--------|------|
| health_score | 95 | ↑ (前 94) |
| governance_anomaly | 100 | → (不变) |
| anomaly_count | 0 | → |
| done tasks | 105 / 105 | ↑ (前 103/104) |
| gac-local-gate | 29/30 PASS | → (cc-switch pre-existing) |

## 3. Task 3: Foundry v2

新增第 10 deck: `bin/decks/port-governance-deck.py`

```
9-deck (Phase 6) → 10-deck (Phase v2):
  + port-governance: hardcoded-ports + env-var-check + cross-repo + catalog health
```

输出到 `runtime/omo/_delivery/foundry/port-governance-{ts}.yaml`。

## 4. 沉淀原则 (P79)

| # | 原则 | 含义 |
|---|------|------|
| P79-1 | **baseline-replay-after-phase** | 每 phase 收口后重放 governance baseline |
| P79-2 | **bin-config-ssot-alignment** | bin/ 和 config/ 的端口引用必须与 port-registry 一致 |
| P79-3 | **foundry-deck-per-governance-axis** | 每治理轴 (X1-X4) 对应一个 foundry deck |
| P79-4 | **catalog-health-metric** | 原则数和 GaC 规则数作为可观测指标写入 foundry metrics |
| P79-5 | **zero-planned-tasks** | 治理收口目标: planned tasks 清零 |
