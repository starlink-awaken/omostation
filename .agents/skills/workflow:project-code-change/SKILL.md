---
name: workflow:project-code-change
description: SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Skill: workflow:project-code-change

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

## Beliefs

### #1 belief-0002
- **Belief**: Workflow run 20260814T122010Z-project-code-change-3e5b45b1 achieved objective: Resume previous interrupted work and continue submodule + governance alignment

### #2 belief-0003
- **Belief**: Workflow run 20260814T122953Z-project-code-change-68d8f7f3 achieved objective: Continue after closeout: keep check-work-landed fix and workspace/runtime updates in governed lane

### #3 belief-0022
- **Belief**: Workflow run 20260824T131143Z-project-code-change-ca90c164 achieved objective: [BET-Y1Q3-T1-11] platform-rebase 独立 clone 退役 provenance 收敛 (Appetite: 1 day)

## Applicable Scope

- `.omo/_delivery/agent-workflows/runs/20260814T122010Z-project-code-change-3e5b45b1.yaml`
- `.omo/_delivery/agent-workflows/runs/20260814T122953Z-project-code-change-68d8f7f3.yaml`
- `.omo/_delivery/agent-workflows/runs/20260824T131143Z-project-code-change-ca90c164.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:project-code-change` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
