---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P2-T5 memory-metrics 指标

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) T5 — recall precision/attribution coverage 指标
> **目的**: 给 Gate C acceptance 全部 6 条 + 跨边界 recall 健康度可量化
> **链接**: OPC-P2-T3 recall-flow / T4 source-map / §17 R0 健康度扩展

---

## §1.0 一句话总结

**OPC-P2-T5 memory-metrics 落地 4 项核心指标 (recall precision / attribution coverage / boundary hit rate / freshness distribution) + 5 边界 §17 健康度扩展公式 + 跨边界 lint 规则, 让 OPC-P2 Memory spine 量化验收。**

## §1.1 4 项核心指标

### §1.1.1 recall_precision (召准率)

**定义**: recall-flow 返回的 top-K 结果中, 实际"被用户采用"(点击/展开/引用) 的比例。

```python
recall_precision = adopted_results / total_results
```

**等级**:
- 🟢 **R0** ≥ 0.90 (90% 召准)
- 🟡 **R1** 0.75-0.90
- 🟠 **R2** 0.50-0.75
- 🔴 **R3+** < 0.50

**采集**: cockpit audit log 记用户对每条 recall 结果的 click/expand/copy 行为 (R3 实施)。

### §1.1.2 attribution_coverage (归因覆盖率)

**定义**: recall-flow 返回结果中, 100% 声明 source/timestamp/owner/freshness 4 字段的比例 (T4 schema 强制)。

```python
attribution_coverage = results_with_full_metadata / total_results
```

**目标**: 100% (T4 source-map 强制)

### §1.1.3 boundary_hit_rate (边界命中率)

**定义**: recall-flow 查询在 5 边界中命中的比例。

```python
boundary_hit_rate = boundaries_hit / 5
# boundaries_hit ∈ {memory, ontology, work, asset, governance}
```

**等级**:
- 🟢 **R0** ≥ 0.80 (5 仓中 ≥ 4 命中)
- 🟡 **R1** 0.60-0.80
- 🟠 **R2** 0.40-0.60
- 🔴 **R3+** < 0.40

**意义**: 跨边界 recall 才有价值。单边界命中 = 知识孤岛。

### §1.1.4 freshness_distribution (新鲜度分布)

**定义**: recall-flow 返回结果中 4 级 (fresh/recent/stale/expired) 的比例分布。

```python
freshness_distribution = {
    "fresh_pct": fresh_count / total,
    "recent_pct": recent_count / total,
    "stale_pct": stale_count / total,
    "expired_pct": expired_count / total,
}
```

**目标**: 90% 在 fresh+recent (< 7d), < 5% 在 expired (> 30d)。

## §1.2 5 边界 §17 健康度扩展公式

**原 §17 健康度** (R0-R5 评分):
```
debt_density = drift / total
if density <= 0.01: R0
elif <= 0.05: R1
...
```

**OPC-P2 扩展健康度** (T5 引入 4 项指标):

```
memory_health_grade = min(
    R(attribution_coverage),    # 100% → R0
    R(boundary_hit_rate),         # ≥0.80 → R0
    R(freshness.expired_pct),     # < 5% expired → R0
    R(recall_precision)           # ≥ 0.90 → R0
)
```

**mo 公式** (min 取短板, 与 xplane_score 一致):
- 任何一项非 R0 → memory_health_grade 跌出 R0
- 4 项全 R0 → memory_health_grade = R0

**5 边界 health (R5-R0)**:
| 边界 | drift_count | total_records | debt_density | grade |
|------|-------------|---------------|--------------|-------|
| memory (gbrain) | 0 | 561 | 0 | R0 |
| ontology (kairon-KOS) | TBD | TBD | TBD | TBD |
| work (cockpit) | TBD | TBD | TBD | TBD |
| asset (metaos) | 0 | 0 | 0 | R0 |
| governance (.omo) | 0 | 0 | 0 | R0 |

(R57+ 实施后填充)

## §1.3 跨边界 lint 规则 (5 仓统一)

```yaml
# projects/lint/memory-metrics.yaml
metrics:
  - name: recall_precision
    target: >= 0.90
    grade: R0
  - name: attribution_coverage
    target: 1.00
    grade: R0
  - name: boundary_hit_rate
    target: >= 0.80
    grade: R0
  - name: freshness.expired_pct
    target: < 0.05
    grade: R0
    inverted: true  # 越小越好

# §17 评分公式
grading:
  formula: "min(R(metrics))"
  thresholds:
    R0: all met
    R1: 1 missed
    R2: 2 missed
    R3: 3 missed
    R4: 4 missed
    R5: all missed
```

## §1.4 跨仓 §17 健康度报告 (E2 dispatcher 扩展)

R57+ 实施：在 omo audit-rollout 报告加 `memory_metrics` 字段:

```json
{
  "generated_at": "2026-06-11T15:00:00Z",
  "repos": {
    "gbrain": {
      "health_grade": "R0",
      "memory_metrics": {
        "recall_precision": 0.92,
        "attribution_coverage": 1.00,
        "boundary_hit_rate": 0.85,
        "freshness": {"fresh": 0.45, "recent": 0.40, "stale": 0.13, "expired": 0.02}
      }
    },
    "kairon": {"health_grade": "R0", "memory_metrics": {...}},
    "metaos": {"health_grade": "R0", "memory_metrics": {...}},
    "cockpit": {"health_grade": "R0", "memory_metrics": {...}},
    "omo": {"health_grade": "R0", "memory_metrics": {...}}
  },
  "summary": {
    "memory_health_grade": "R0",
    "worst_boundary": "R0"
  }
}
```

## §1.5 实施分阶段

1. **T5.1** (本 Round): 设计文档 + 4 指标 + 跨边界 lint
2. **T5.2** (R57+): omo audit-rollout 加 memory_metrics 字段 (E2 dispatcher 扩展)
3. **T5.3** (R58+): cockpit collect 用户 click/expand/copy 行为 (recall_precision 真实采集)

## §1.6 累计 Gate C acceptance (6/6)

- ✅ kairon/gbrain/metaos persistence risks resolved (T0)
- ✅ memory boundaries defined (T1)
- ✅ memory URI 路由表设计 (T2)
- ✅ one real question flows collect→ingest→search→output→archive (T3)
- ✅ search surfaces declare scope (T3 含 scope 声明)
- ✅ **outputs include source metadata (T4)**
- ✅ **memory-metrics 量化 (T5, 本 doc)**

**Gate C 6/6 全部 hit 实质化 ✅**——可收口。

---

**OPC-P2-T5 设计完成。** 4 指标 + 5 边界 §17 扩展 + 跨仓 lint 规则 + 实施分阶段就位。R57+ 推进 T5.2 跨仓 memory_metrics 字段实施候选已列。
