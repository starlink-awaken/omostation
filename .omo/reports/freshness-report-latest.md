# Freshness Report

Generated: 2026-06-05T06:12:34.787931+00:00

## Summary

| Category | Count |
|----------|-------|
| 🟢 FRESH (<7d) | 10 |
| 🟡 STALE (7-30d) | 0 |
| 🔴 ANCIENT (>30d/missing) | 4 |
| **Total** | 14 |

## Fresh Items

| ID | Title | Status | Age (days) |
|----|-------|--------|------------|
| DEBT-OMO-001 | 集成测试依赖真实 .omo 工作区状态 | identified | 0 |
| DEBT-OMO-006 | X1: 沙箱空转 — KEI sandbox registered but never executed audit | identified | 0 |
| DEBT-OMO-007 | L0: 协议幽灵 — 16个协议中只有MCP真正在用 | identified | 0 |
| DEBT-OMO-008 | L1: 调度器缺失 — 无统一任务调度机制 | identified | 0 |
| DEBT-OMO-009 | L1: 健康检查陈旧 — health check data outdated | identified | 0 |
| DEBT-OMO-010 | X2: 无保鲜实现 — no freshness validation mechanism in place | identified | 0 |
| DEBT-OMO-011 | X1: 无审计链 — no audit chain established | identified | 0 |
| DEBT-OMO-012 | X3: 无成本追踪 — no cost tracking mechanism | identified | 0 |
| DEBT-OMO-013 | L0: TaskObject未实际使用 — TaskObject defined but never adopted | identified | 0 |
| DEBT-OMO-014 | X1-AUTH-001: 身份追踪 — 债务变更无操作者记录 | identified | 0 |

## Ancient Items

| ID | Title | Status | Reason |
|----|-------|--------|--------|
| DEBT-OMO-002 | CLI 入口损坏: scripts/omo_debt.py 不存在 | closed | no timestamp |
| DEBT-OMO-003 | test_omo_automation.py 仍依赖 scripts.sync_omo_state (sys.path.insert) | closed | no timestamp |
| DEBT-OMO-004 | I0: Agora SSE不可达 (Agora SSE endpoint unreachable) | closed | no timestamp |
| DEBT-OMO-005 | I0: Agora双实例 — native + Docker 并行运行冲突 | closed | no timestamp |

