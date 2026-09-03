---
name: workflow:bet-execution
description: SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取
category: SEMA-Crystallized-Skill
type: ssot
owner: agent-skills-team
last_updated: 2026-09-03
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

### #3 [warning]
- **Pitfall**: Unverified workflow closeout
- **Solution**: Executed agent-workflow verify & observe pass

## Beliefs

### #1 belief-0005
- **Belief**: Workflow run 20260901T010516Z-bet-execution-c2125a72 achieved objective: [BET-Y1Q4-T2-03] 纸质公文扫描件多模态 OCR 结构化提取与版面保真还原 (Appetite: 2 days)

### #2 belief-0006
- **Belief**: Workflow run 20260901T030710Z-bet-execution-7949aad4 achieved objective: [BET-Y1Q4-T8-03] 标准红头公文排版 DOCX、高管技术汇报 PPT 与矢量图表一键生成导出 (Appetite: 2 days)

### #3 belief-0007
- **Belief**: Workflow run 20260901T053633Z-bet-execution-d17d23a1 achieved objective: [BET-Y1Q4-T2-02] 微信/企微/飞书即时通讯会话感知与指令式即时办结 (Appetite: 2 days)

## Applicable Scope

- `.omo/_delivery/agent-workflows/runs/20260901T010516Z-bet-execution-c2125a72.yaml`
- `.omo/_delivery/agent-workflows/runs/20260901T030710Z-bet-execution-7949aad4.yaml`
- `.omo/_delivery/agent-workflows/runs/20260901T053633Z-bet-execution-d17d23a1.yaml`

## Standard Workflow

1. Run `make gac-local-gate` — all checks must pass.
2. For `workflow:bet-execution` changes, use isolated worktree.
3. Verify with targeted tests before expanding scope.
