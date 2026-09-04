---
title: BET-Y1Q3-T6-02 复盘 — cockpit Phase 4 清理债务
type: retro
owner: governance-team
created: 2026-08-16
context: >-
  Phase 4 (cockpit_mcp 退役) 遗留三件: 残留 import / l4bridge 降级 / 指针同步。
  老王亲推 (subagent 故障期), 落地于本 worktree。
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T6-02 复盘

## 核验与交付 (2026-08-16)

| done_when | 结果 | 证据 |
|---|---|---|
| cockpit_mcp 残留 import 清理 | ✅ 生产代码零残留 | 唯一命中是 tests 守护断言 (test_no_production_reference_to_removed_cockpit_mcp, 防复活) — 非清理对象, 是保护 |
| l4bridge 降级移除 | ✅ 5 处全清 (-30/+10) | workspace_context/domains_list/cards_check/cards_status/skill 调度段, 异常改走 CLI 顶层非零退出 |
| c2g+bus-foundation 指针同步 | ✅ 零漂移 | git submodule status 前缀空 (main 已同步, 立账时的漂移已被后续 PR 修) |
| 六模块无参运行 | ✅ 全 rc=0 | context/cards/vault/domains/health/mcp 实跑输出正常 |

cockpit 子仓: l4bridge 降级移除 commit 已推子仓 main; 主仓指针 bump。

## Q1-Q5 简答
- Q1: 0.3h vs appetite 3d — 三件债两件已被时间解决, 真正剩的只有 l4bridge 降级。
- Q2: 四条全过 (上表)。
- Q3: 立账审计与执行的时间差再次证明「candidate 期的债会被后续轮次顺手还」——收口前实跑 verify 是唯一可信路径。
- Q4: -30 行 (净减), 治理面收紧。
- Q5: 后续 cockpit 治理面调用新增时, 禁止再加 defensive fallback 吞异常 (守护测试可扩展覆盖 l4bridge)。
