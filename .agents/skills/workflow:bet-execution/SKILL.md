---
name: workflow:bet-execution
description: SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill
---

# Skill: workflow:bet-execution

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
- **Belief**: Workflow run 20260807T063711Z-bet-execution-66b7ef2c achieved objective: BET-Y1Q1-T1-07 git 入口收口

### #2 belief-0002
- **Belief**: Requirement iteration edits must claim path and start agent-workflow run first
- **Pitfall**: Direct edit without agent-workflow claim triggers compliance gate halt
- **Solution**: Always run agent-workflow start and claim before editing requirement files

### #3 belief-0003
- **Belief**: Workflow run 20260807T130548Z-bet-execution-be3544c4 achieved objective: 全域 scene card v2 升级

## Applicable Scope

- `.omo/_delivery/agent-workflows/runs/20260807T063711Z-bet-execution-66b7ef2c.yaml`
- `.omo/_delivery/agent-workflows/runs/20260807T130548Z-bet-execution-be3544c4.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:bet-execution` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
