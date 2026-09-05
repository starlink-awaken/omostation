---
name: workflow:governance-state-mutation
description: SEMA 自动结晶技能包 — 基于 5 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Skill: workflow:governance-state-mutation

> Auto-crystallized by SEMA engine from agent pitfall experience.
> Source: .omo/state/agent-beliefs/index.yaml

## Pitfalls & Solutions

### #1 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

### #2 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

### #3 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

### #4 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

### #5 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

## Beliefs

### #1 belief-0005
- **Belief**: Workflow run 20260814T123541Z-governance-state-mutation-f3dfe789 achieved objective: Converge governance/runtime diff set to clear ADR-0203 requirement scope

### #2 belief-0006
- **Belief**: Workflow run 20260814T123841Z-governance-state-mutation-9890ead1 achieved objective: Prepare final mainline PR for remaining root-level governance/runtime convergence changes

### #3 belief-0014
- **Belief**: Workflow run 20260820T063442Z-governance-state-mutation-743ac648 achieved objective: [BET-Y1Q3-T6-12] MOSBeliefManager 运行时计数写入 runtime truth 而非 SSOT registry (Appetite: 1 hour)

### #4 belief-0015
- **Belief**: Workflow run 20260820T070722Z-governance-state-mutation-cc7a3f63 achieved objective: 归档 bin/bc-os/ 下当前无外部引用的 3 个脚本（apple_mail_watcher/l3_smart_router/lifecycle_changer），减少活跃脚本表面积

### #5 belief-0019
- **Belief**: Workflow run 20260821T132302Z-governance-state-mutation-f8c28458 achieved objective: [BET-Y1Q3-T1-09] D4 逃生口固化 — 权限类 vs fingerprint 债 + 观察再跳 + 人类口硬拒 (Appetite: 1 day)

## Applicable Scope

- `.omo/_delivery/agent-workflows/runs/20260814T123541Z-governance-state-mutation-f3dfe789.yaml`
- `.omo/_delivery/agent-workflows/runs/20260814T123841Z-governance-state-mutation-9890ead1.yaml`
- `.omo/_delivery/agent-workflows/runs/20260820T063442Z-governance-state-mutation-743ac648.yaml`
- `.omo/_delivery/agent-workflows/runs/20260820T070722Z-governance-state-mutation-cc7a3f63.yaml`
- `.omo/_delivery/agent-workflows/runs/20260821T132302Z-governance-state-mutation-f8c28458.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:governance-state-mutation` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
