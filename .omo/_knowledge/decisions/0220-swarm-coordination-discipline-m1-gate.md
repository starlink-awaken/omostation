---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-17
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0218-agent-isolation-p0-verify-and-hygiene.md
  - 0202-fake-green-prevention.md
  - ../patterns/p73-truth-driven-engineering-pattern.md
supersedes: []
---

# ADR-0220: Swarm 协调纪律 — M1 收口前置

> **背景**: 编号 0220。本 ADR 是 ADR-0210 收敛期 M1 门禁「并发 agent
> 主仓冲突 = 0」的收口前置（G-CONV.7）。

## Context and Problem Statement

隔离机制（worktree + pre-push blocking，ADR-0218）已装，但并发 swarm 仍制造冲突：
ADR 抢号、分支挪用、无 claim 共享写、escape-hatch 滥用。机制齐全 ≠ 冲突归零——
缺的是**强制协调纪律**。

## Decision Outcome

**选定 B — 强制协调纪律，四条闸门 + 一条收口判据**（实现见 registry + CLI）:

| Gate | SSOT | Entry / check |
|------|------|----------------|
| D1 ADR 原子申请 | `.omo/_truth/registry/swarm-coordination.yaml` | `next-adr-id.py --claim` + flock |
| D2 分支占用锁 | 同上 + `.omo/_delivery/branch-claims/` | `gac-worktree.sh claim` |
| D3 共享 worktree claim | 同上 | pre-commit `swarm-claim-check` |
| D4 escape-hatch | 同上 `escape_hatch_exemptions` | pre-push `CI_LOCAL_SKIP` + CLI |

实现模块:

- `bin/gac/swarm_discipline.py` — 纯决策 + 锁/事件
- `bin/gac/swarm-discipline-cli.py` — 可执行校验入口
- 冲突事件: `.omo/_delivery/swarm-conflicts/events.jsonl`
- 观测窗: `swarm-discipline-cli.py window-start|window-status`

### 收口判据（M1「冲突=0」）

72h 观测窗内真实主仓冲突事件数 = 0 → 方可宣布 M1 冲突达标并进兑现期。
窗未满或 count>0 → **不得**宣布达标。

## Confirmation

- [x] 四闸门 registry + fail-closed 校验入口已落地
- [x] 单测覆盖 D1–D4 违规拒绝 / 合规放行
- [ ] 72h 窗冲突计数 = 0（上线后观测，非本 PR 伪造）

---

*ADR-0220 · ACCEPTED (implementation) · 2026-07-17 · 夏明星 · G-CONV.7*
