---
status: active
lifecycle: retrospective
owner: governance-team
last-reviewed: 2026-07-02
related:
  - ../decisions/0122-system-audit-followup-plan.md
  - 0124-s1-followup-retrospective.md
  - ../patterns/p72-follow-up-completion-pattern.md
---

# ADR-0125: S2 阶段 S1 部分完结复盘 — F-2 + ADR-0115 Phase 2/4 (5 commit, 1 PR)

- **Status**: ACTIVE
- **Date**: 2026-07-02
- **Authors**: governance-team (基于 ADR-0122 S2 路线图执行结果)
- **Supersedes**: —
- **Related**: ADR-0122 (S2 路线图) / ADR-0124 (S1 复盘) / P72 (follow-up completion)

## Context and Problem Statement

ADR-0122 S2 阶段 (3-4 周, 3 PR + ADR-0115 Phase 2/4) 范围明确:
F-2 (state-freshness + 8 initiative 进度填充) / F-8 (BOS kind 跨仓)
/ F-13 (omo-debt 收编) / ADR-0115 Phase 2 (gov- rename)
/ ADR-0115 Phase 4 (4 dashboard 合并).

本 ADR 复盘 S2 阶段首日落地: F-2 (3 步全部) + ADR-0115 Phase 2 (X-Plane
落 2 个 commit) + ADR-0115 Phase 4 partial (2/4 合并). F-8/F-13 跨仓
(ADR-0122 明确"❌ 跨仓 F-7/F-8/F-13 不属主仓 scope") 留 S2 后续. 
governance score 回升留 S2 (依赖 service online ratio, 非主仓可控).

## Decision Summary

### S2 阶段首日 5 commit (1 PR)

| Commit | 项 | 内容 |
|--------|---|------|
| `fdcfdfe0` | F-2 step 1+2 | `bin/state-freshness-check.py` 新建 (ADR-0119 S2-5) + 接入 `gac-local-gate.py::CHECKS` (S2-6) + `change-lane-check.py` lane 显式列 |
| `40ee939e` | F-2 step 3 | governance-evolution 8 initiative 进度填充 + 7/8 next_step 补全 (1/8 已有) |
| `011cb271` | ADR-0115 Phase 2 | X-Plane: `gov-history-stats.py` → `governance-history-stats.py` + `gov-trend-report.py` → `governance-trend-report.py` (2 rename) |
| `8b5e50b6` | ADR-0115 Phase 2 整理 | `change-lane-check.py` 显式列 3 个 governance-* 工具, 避免误归 code lane |
| `7db30eef` | ADR-0115 Phase 4 partial | `governance-dashboard.py` 加 `--readiness-summary` / `--ui-render` 子命令 (合并 2/4 dashboard 工具) |

### 关键治理成果

#### F-2 step 1+2: state-freshness 独立化

**问题**: `compass_radar.py` 内含 freshness_score 但耦合在复合 health_score 计算.
gac-local-gate 默认 mode 不可见状态面 stale 状态.

**治本**: 新建 `bin/state-freshness-check.py`:
- 独立检查 5 个状态面 SSOT (health / system_health / governance.jsonl / 
  debt-dashboard / governance-data) 的 generated_at 新鲜度
- 阈值 (与 compass_radar 一致): ≤1h=100 / ≤24h=80 / ≤7d=50 / >7d=0
- 退出码: 0=全新鲜 / 1=有 stale / 2=有 expired
- 接入 gac-local-gate CHECKS (默认 mode 跑, 派生快照 stale 不可缺)

#### F-2 step 3: governance-evolution 进度填充

8/8 active initiative 加 next_step (1/8 已有 → 8/8):
- worktree-release-convergence: 30% (PR #19 F-12 治本)
- cockpit-governance-status-plane: 25% (cockpit-team 入口待)
- claim-policy-tiering: 35% (P72 原则 4 lane 单 commit 实例化)
- bos-governance-evolution-routes: 45% (6 BOS URI 路由已注册)
- capability-traceability: 55% (F-6 6/7 + F-2 7/8)
- governance-operating-rhythm: 75% (F-2 step 1+2+3 本 PR)
- golden-path-e2e: 75% (5 PR 闭合 S0+S1+S2 部分)
- entrypoint-convergence: 80% (3 入口收敛)

#### ADR-0115 Phase 2: gov- → governance- rename

X-Plane commit `011cb271` 完成 2 个 rename:
- `bin/gov-history-stats.py` → `bin/governance-history-stats.py`
- `bin/gov-trend-report.py` → `bin/governance-trend-report.py`

本 PR 补 commit `8b5e50b6` 整理: `change-lane-check.py` 显式列 3 个 governance-*
工具, 跟 governance-evolution / governance-semantic-gate 同档 (避免按 *.py 默认
规则归 code lane).

#### ADR-0115 Phase 4 (partial): dashboard 合并

4 个 dashboard 工具合并, 2/4 落地:
- `dashboard-readiness-summary.py` → `--readiness-summary` (合并)
- `dashboard-ui-render.py` → `--ui-render <HTML>` (合并)
- `gac-dashboard.py` → 留独立 (GaC 健康, 跨文件引用 50+ 行, 留 follow-up)

实现: wrapper 模式 (合并入口但留独立文件), 不破坏原 P86 wrapper 行为 (无 flag 时
仍跑 19 工具仪表盘).

### 留 S2 follow-up

- **F-8** (BOS kind 标签, 6 单点域加 kind): 跨仓 (agora/omo/cockpit 团队), 
  ADR-0122 明示 "❌ 跨仓 F-7/F-8/F-13 不属主仓 scope", 留 S2 后续 PR 触发
  跨仓协调
- **F-13** (omo-debt 收编 cockpit): 跨仓, 同 F-8 留
- **F-2 续**: governance score 回升 (依赖 service online ratio, 非主仓可控)
  + planned task 收口 (11/106, 治理面工作, 留 S2)
- **ADR-0115 Phase 4 续**: 走完全合并路径 (a) 移 gac-dashboard 内容
  (b) 删 3 个被合并的独立 bin 文件 (c) 更新所有 caller
- **S2 F-14** (本 S1 阶段提): sub-tools 漂移治本 (gac-bootstrap / gac-executor
  / mof-schema-validate / adr-coverage) — S1 F-5 + M2 enum 修后大部分治本
  (governance-semantic-gate 在 M2 enum 修后 strict 模式 PASS), 留 S2 收尾

## 验证状态

### Final gate (PR #21 落地后)

- `make gac-local-gate`: PASS (16/16, +1 state-freshness-check)
- `ssot-guardian`: PASS
- `governance-evolution validate`: PASS (8/8 initiative schema)
- `governance-evolution status`: next_active 8/8 有 next_step
- AST audit: 0 误报
- 5 commit lane 守门: governance_code × 3 (F-2 step 1+2 / change-lane / Phase 4)
  + governance_state × 1 (F-2 step 3) + 1 X-Plane

### S2 路线图状态

```
S2 中期 (3-4 周, 3 PR + ADR-0115 Phase 2/4)
  ✅ F-2 step 1+2: state-freshness 独立 + 接入 gac-local-gate (本 PR)
  ✅ F-2 step 3: governance-evolution 8 initiative 进度填充 (本 PR)
  ✅ ADR-0115 Phase 2: gov- → governance- rename (X-Plane 011cb271)
  ✅ ADR-0115 Phase 2 整理: change-lane-check 显式列 (本 PR)
  ✅ ADR-0115 Phase 4 partial: 2/4 dashboard 合并 (本 PR)
  ⏳ F-8 (BOS kind 跨仓): 留 S2 后续
  ⏳ F-13 (omo-debt 收编跨仓): 留 S2 后续
  ⏳ F-2 续 (governance score 回升 + planned 收口): 留 S2
  ⏳ ADR-0115 Phase 4 续 (gac-dashboard 完全合并): 留 S2
```

## 链接

- ADR-0122: S2 路线图 (F-2/F-8/F-13/ADR-0115)
- ADR-0124: S1 阶段完结复盘
- P72: follow-up-completion-pattern
- PR #20: S1 复盘
- PR #21 (本 S2 阶段): F-2 + Phase 2 整理 + Phase 4 partial
- X-Plane #21... (跨 S2 阶段 worktree)

## Follow-up (S2 阶段续)

### 主仓 scope (本 S2 后续 PR)

- ADR-0115 Phase 4 续: gac-dashboard 完全合并 (跨文件 50+ 行, 风险评估)
- F-2 续: governance score 回升 (service online ratio 启 daemon)
- F-2 续: planned task 收口 (11/106 治理面工作)
- sub-tools 漂移收尾 (S2 F-14)

### 跨仓 scope (主仓触发跨仓协调 PR)

- F-8: 6 BOS 域 (cockpit / l4-kernel / runtime / meta / swarm / omo) 加 kind
- F-13: omo-debt 收编 cockpit (registry 同步 + 删独立仓)

💘 Generated with Crush

Assisted-by: Crush:MiniMax-M3
