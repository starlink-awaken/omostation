---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
related:
  - 0202-fake-green-prevention.md
  - 0215-agora-gateway-false-green-pid-health-check.md
  - 0179-runtime-probe-false-positive-treatment.md
supersedes: []
---

# ADR-0216 — compass 健康刷新：feedback partial smoke + c2g 降级

- **Status**: ACCEPTED
- **Date**: 2026-07-15

## Context

复合健康分长期 ~83，甚至刷新后跌到 **50**。根因不是 runtime 全死，而是：

1. `evidence-smoke` 在 worktree 未装 `pydantic/fastmcp` 时 **import agora 失败直接 return error**，**不带 `feedback_loop`**
2. `compass_radar._collect_feedback_liveness` 见非 0 exit → **判定 feedback 死 → 复合分硬封顶 50**
3. worktree 默认不 init `projects/c2g` → `ModuleNotFoundError: c2g` 使 radar 完全无法跑
4. freshness 用**写前**旧 `health.yaml` 年龄计分，单次刷新后复合分仍带旧 freshness 惩罚

## Decision

### D1 — evidence-smoke partial 报告

agora import 失败时仍产出 JSON：`partial: true` + `feedback_loop` + `working_tree`（BOS 维 skipped）。`--json` 模式 exit 0，供 compass 消费。

### D2 — compass feedback fallback

smoke 失败或无 feedback 字段时，本地读 `governance-history.jsonl` / `omo-events.jsonl`（与 smoke 同源 24h 规则），**禁止**因依赖缺失误封顶。

### D3 — c2g 降级审计

`c2g.strategy` import 失败时返回 empty task audit（anomaly_count=0）并打印 init 提示，仍可算 runtime/freshness 复合分。

### D4 — freshness 在本轮 regenerate 记 100

本 run 写入 `generated_at=now`，复合分用 freshness=100；`prior_freshness_*` 保留诊断。

## Evidence (this worktree)

```
health_score (composite): 100/100
governance_anomaly_score: 100
service_online_ratio: 100%
freshness_score: 100 (regenerated-now)
feedback partial: alive=True
```

## Consequences

- worktree/CI 缺 agora venv 不再把 health 假打死到 50
- BOS 全量 resolve 仍需 agora deps；partial 只保证 feedback 真同源
