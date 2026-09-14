---
name: workflow:mini
description: SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill

last-reviewed: 2026-08-26
type: ssot
owner: governance-team
---

# Skill: workflow:mini

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

### #1 belief-0005
- **Belief**: Workflow run 20260808T014350Z-mini-8e03c676 achieved objective: closeout test

### #2 belief-0006
- **Belief**: Workflow run 20260808T051020Z-mini-e185b394 achieved objective: closeout test

## Applicable Scope

- `/private/var/folders/2s/pr52f6ys76v__sm_q1fkv_n40000gn/T/pytest-of-xiamingxing/pytest-118/test_closeout_verifies_observe0/runs/20260808T014350Z-mini-8e03c676.yaml`
- `/private/var/folders/2s/pr52f6ys76v__sm_q1fkv_n40000gn/T/pytest-of-xiamingxing/pytest-148/test_closeout_verifies_observe0/runs/20260808T051020Z-mini-e185b394.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:mini` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
