---
name: workflow:governance-state-mutation
description: SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill
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

## Beliefs

### #1 belief-0001
- **Belief**: Workflow run 20260819T031223Z-governance-state-mutation-2f4cb4e1 achieved objective: [BET-Y1Q3-T6-07] 根目录与项目废弃面清理 (Appetite: 2 days)

### #2 belief-0002
- **Belief**: Workflow run 20260819T071306Z-governance-state-mutation-20dd24d7 achieved objective: [BET-Y1Q3-T6-08] GaC 本地门禁剩余债务清理 (Appetite: 4 hours)

## Applicable Scope

- `.omo/_delivery/agent-workflows/runs/20260819T031223Z-governance-state-mutation-2f4cb4e1.yaml`
- `.omo/_delivery/agent-workflows/runs/20260819T071306Z-governance-state-mutation-20dd24d7.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:governance-state-mutation` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
