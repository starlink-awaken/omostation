---
status: active
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-15
---

# ADR-0195 — Architecture Convergence (ISC-2): 声明/执行鸿沟收敛

> **Status**: ACTIVE · **Created**: 2026-07-14
> **Phase**: 43 · **Priority**: P0
> **关联**: #353 eCOS v6 架构分析, ARCHITECTURE-ANALYSIS-2026-07-14.md

---

## 问题

声明/执行鸿沟贯穿整个 eCOS 架构：

| 声明面 | 声明值 | 执行面 | 实测 |
|:-------|:------:|:-------|:----:|
| `ecosystem_maturity_score` | 100 | 健康分 (ISC-2) | **68** |
| `governance_anomaly_score` | 100 | daemon 在线率 | **44%** |
| `debt_health` | 100 | debt_adjusted_health | **61.6** |
| `service_online_ratio` | 60% | 可观测性 | 4/9 扫描 |

根因：健康分公式 `ISC-1 = governance×0.5 + freshness×0.2 + runtime×0.3` 被声明面权重 0.5 主导，
导致系统看起来健康但实际执行面偏差 38 分。

## 决策

**ISC-2: 反向权重分配**

```
ISC-2 = governance×0.3 + freshness×0.2 + runtime×0.5
          30.0    +   16.0      +   22.0      = 68.0
```

- governance 权重 0.5→0.3（声明面不再主导）
- runtime 权重 0.3→0.5（执行面说了算）
- freshness 0.2 不变

## 配套变更

1. **健康扫描间隔 900→60 s** — 修复后自愈等待 15 分钟→1 分钟
2. **BOS 追踪门禁** — `bos-tracking-gate.py` 防止追踪文件漂移
3. **正式债务登记** — 8 项真实债务写入 `debt.yaml`
4. **Submodule drift 巡检** — `+` drift 从 3→0

## 收敛标准

| 指标 | ISC-1 | ISC-2 | 目标 (P44) |
|:-----|:-----:|:-----:|:----------:|
| 健康分 | 84 (虚高) | 68 | 75 |
| debt_adjusted | 61.6 | 61.6 (待重算) | 70 |
| daemon 在线率 | 60% | 44% | 90% |
| unassigned | 35 | 15 | 5 |
| 债务项 | 0 | 8 | 12 |
| 扫描延迟 | 900s | 60s | 30s |

## 风险

- ISC-2 暴露后分数下降可能触发 false alarm
- 真实债务登记后 `debt_health` 从 100 下降
- 扫描间隔缩短增加 CPU 开销 ~15×（900→60s）

## 回退

恢复 `health.yaml` 权重为 ISC-1 原始值，`health_scan.py` INTERVAL 回 900。
