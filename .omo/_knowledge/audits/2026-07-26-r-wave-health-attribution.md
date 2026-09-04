---
last_updated: 2026-08-25
lifecycle: history
owner: unassigned
---

# R 波 health 93→96 归因审计 (2026-07-26, Round 3)

> profile: governance-agent · run: 2827d190 · 红线守: 未放宽 ADR-0242/P0-5 门, 未恢复 CI ignore

## 现象
- health.yaml (00:43:52, Phase 0 并发期): health **93**, anomaly 77, concurrent_conflicts=1
- compass 实时 (03:45:35 重跑): health **96**, anomaly 85, concurrent_conflicts=0

## 扣分链 (93 时)
governance_execution_surface: base_anomaly 85 − execution_deduction 8 (concurrent_conflicts=1 × weight 8) = anomaly 77
→ governance 贡献 23.1 (0.3×77) → health ≈ 23.1 + 20 (freshness) + 50 (runtime) = 93

## 三分类归因
| 类 | 结论 | 依据 |
|----|------|------|
| A 真实退化 | ❌ 无 | 无新引入持续问题 |
| B 诚实化下探 | ❌ 无 | ADR-0242 漂移门 + P0-5 防复发门均 **required:false, 不进 health 计算**. 门没压分. |
| C 口径误报 | ✅ 主导 | concurrent_conflicts=1 是 Phase 0 多 run 并发瞬态; closeout 后 active_runs=1 → run_pressure=0; health.yaml 缓存滞后未刷新. |

## concurrent_conflict 检测 (compass_radar.py:185)
`run_pressure = max(0, active_runs − 1) + wt_pressure = max(0, worktrees − 2)`
- 00:43:52: active_runs>1 (a408c2f1 + 并发 run) → pressure 1
- 现在: active_runs=1 (仅 2827d190), abe091ce 已 closeout(status=ok) → pressure 0

## 处置 (R2)
- 重跑 compass 刷新 health.yaml = 96 (≥95) ✓
- 建议: health.yaml 定期刷新机制 (避免缓存滞后再次触发 health<95 熔断误判)
- 红线守: 未改 compass 逻辑 / 未放宽门 / 未删冲突计数. health 96 是真实计算值.

## R3 · Round 2 C 波核实
- PR #509 (ingress-registry) **MERGED** ✓
- PR #510 (5角色协作批次 ADR-0235) **MERGED** ✓
- 协作管线实装: bin/delivery/ (collab_cli / role_collab / failover_drill / emergence) ✓
- 失败路径测试 (≥5 场景): **未明确确认** (failover_drill.py 可能部分覆盖, 需 Round 3 C 波补完)

## 结论
health 真实 **96** (≥95). 93 是 C 类缓存滞后 (并发瞬态 + health.yaml 未刷新),
**非 A 退化, 非 B 诚实下探**. workorder 初始判断"很可能是诚实化下探"被推翻 ——
上一轮加的门 required:false 根本不进 health 计算. 不需新基线说明, 不需调 95 阈值.
**R 波验收: health ≥95 ✓, C 波解锁.**
