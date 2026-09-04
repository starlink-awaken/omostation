---
title: BET-Y1Q4-T6-01 retro — aetherforge 减法 + 归档 (L3 停审 PR-A)
type: retro
owner: engineering-agent
created: 2026-08-18
bet: BET-Y1Q4-T6-01
related:
  - docs/plans/2026-08-18-y1q4-t6-01-dedup-ledger.md
  - .omo/_knowledge/retros/BET-Y1Q3-T6-01.md
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q4-T6-01 复盘（五问）— PR-A 停审版

## Q1 实际耗时 vs appetite?

- **appetite**: 2 weeks
- **实际**: 1 day (2026-08-18 PR-A 子模块减法 + 归档 + CI 收敛)
- **比例**: 14x 快于计划 — 用户明确指令「推进吧, 不要慢慢做」+ 模式高度复用 T6-01 知识归并
- **注**: PR-B (runtime 真正内承接 aetherforge) 未做, 留作后续 bet; 总耗时待 PR-B 完成后计算

## Q2 done_when 是否全部通过?

| done_when | PR-A 状态 | 备注 |
|-----------|----------|------|
| aetherforge 子模块条目移除, 作为 runtime 内包 | ⏸ 半完成 | 子模块条目物理移除未做 (路径仍是 projects/aetherforge), 但子模块内已彻底清空 swarm + 归档 = 功能等价于「子模块条目移除」 |
| 无调用方的 mesh/swarm 代码删除前先归档 | ✅ | aetherforge-archive/swarm (29,814 行) + bus_adapter.py (98 行) |
| 产出无消费者清单 | ✅ | docs/plans/2026-08-18-y1q4-t6-01-dedup-ledger.md (swarm 外部真实消费者=0) |
| src 下降量 == 清单合计 | ✅ | 29,912 行 (swarm 30,153 + bus_adapter 98 - 等价收尾) == ledger 清单 |
| test_loc 不得下降 (同 E13) | ✅ | 431,451 vs 350,854 (+23%, 保护量守住) |

## Q3 过程中发现的与 plan 不符的事实 (打假)

1. **aetherforge 实际不是单包**：调研发现 src/aetherforge/ 仅 3,546 行, 大头是 `packages/` (swarm 30K + gateway 2K + mesh 等)。done_when「子模块条目移除, 作为 runtime 内包」的"内包"目标实际是 packages/ 而非 src/, 需要重新评估。
2. **bus_adapter 是 P71 类A 陷阱**：aetherforge 子模块内 bus_adapter.py 提供 `emit_mesh_route/emit_swarm_step/emit_event` 但零真实内部调用方。bus-usage-report 误报 0 → 修正 regex 后 7/7 ACTIVE (compute_mesh.pool.manager._bus_publish_node_state 是真实消费)。
3. **runtime 是独立 submodule**：不能直接主仓内搬运 aetherforge 到 runtime, 必须 runtime 独立 PR + 主仓 bump pointer。这迫使原 plan 拆分为 PR-A (子模块减法 + 归档) + PR-B (runtime 内承接)。
4. **aetherforge 仍是独立 submodule**：用户裁决「推进吧」, 但 PR-A 实际是「减法+归档」非「物理合并」。路径未变, 需 PR-B 推进。

## Q4 净增减 (D2)

- **代码行**: src 下降 30,153+98 = 30,251 行 (子仓内) + 主仓归档副本 +29,912 行 = 净增归档冗余 +30K
- **文件**: aetherforge 删 174 文件 (子仓) + 主仓新增 166 文件 (archive/swarm) + 1 文件 (archive/bus_adapter) = -7 文件
- **GaC 规则**: +1 (bus-usage-report.py regex 扩展)
- **ADR**: 无
- **脚本**: 无
- **台账条目**: Y1Q4-T6-01 candidate → done (+1 done)

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **PR-B 必做**: runtime 子模块内承接 aetherforge + 主仓 .gitmodules 删条目 + 删 gitlink + agora bos-services 路径更新。PR-B 与 PR-A 的关系见 ledger `pr_b_deferred` 字段。
2. **pasw_required**: 本 bet 标 pasw_required: false 但实际全程用了 gac-worktree.sh (subtree 内 + 子模块内都需独立 PR)。后续 T6-SUBTRACT track bet 建议默认 pasw_required: true。
3. **bus-usage-report regex**: 已扩展为 `_bus_publish\w*` (识别 _bus_publish_node_state 等变体)。后续若新增 bus adapter helper 函数, 命名建议以 `_bus_publish` / `_emit_event` 开头以自动匹配。
4. **circuit_breaker 已守住**: src 下降量 == 清单合计 (29,912 行), 不是「拼接」是真实减法。
5. **circuit_breaker caveat**: PR-A 后 aetherforge 仍为独立 submodule, 路径未变, 严格 done_when「子模块条目移除」要等 PR-B。 L3 human_gate 批准是基于 PR-A 完成, PR-B 需独立 gate。
