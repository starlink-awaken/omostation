---
schema_version: specification/v1
spec_version: 1.0.0
title: Agora A2A 双向任务委派与 Resident Agent Card 协议接入
bet_id: BET-Y1Q4-T5-03
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-11
---


# Agora A2A 双向任务委派与 Resident Agent Card 协议接入（BET-Y1Q4-T5-03）

## 背景（Context）

Agora 已有 A2A 任务原语（`a2a_send_task` / `a2a_get_task` / `a2a_list_tasks` /
`list_agent_cards` / `get_agent_card`，见 `projects/agora/src/agora/server/tools_governance.py`），
但外部瞬态 Agent（Antigravity、Claude Code、Codex）无法发现常驻 Agent，
也无法通过 A2A 向其委派长时后台任务：`list_agent_cards` 只收敛已注册 service，
无 `resident-orchestrator` 卡片；`resident.*` 工具名经核心 Router 派发无归宿。
本 spec 为 BET-Y1Q4-T5-03 建立契约：ledger `goal/done_when/verify` 为准，
`write_surfaces` 收敛到 `tools_governance.py`、`tools_resident.py`、
`tests/test_resident_a2a.py` 与 retro。

## 目标（Goal）

在 Agora MCP 中注册 resident-orchestrator 的标准 Agent Card（支持后台分析、
深度巡检、对账等技能）；打通外部瞬态 Agent 通过 `a2a_send_task` 直接向常驻
Agent 委派长时后台任务，并通过 `a2a_get_task` 追踪进度与获取产物。

## 非目标（Non-Goals）

- 不重构 Agora 既有 A2A 核心调度协议（`metaos.a2a.task_manager` 与核心 Router 不动）。
- 不改变瞬态 Agent 自身的工作流生命周期。

## 完成标准（Done When）

1. `list_agent_cards` 工具输出包含完整的 resident-orchestrator 卡片元数据及 Capabilities。
2. 支持通过 `a2a_send_task` 提交 resident 任务并返回有效 task_id 与状态跟踪。
3. Agora 单元测试与集成测试验证 A2A 委托与结果拉取闭环全部通过。

## 设计决策（Decisions）

1. `resident-orchestrator` 卡片为 well-known 规范卡（name / skills /
   capabilities / endpoint 元数据），`list_agent_cards` / `get_agent_card`
   恒返回；若 registry 未来注册同名 service，则以 registry 实时数据优先合并。
2. `a2a_send_task` 对 `resident.*` 工具名做本地短路派发（`resident.status` /
   `resident.roles` 起步），复用 `tools_resident.py` 的实现函数，不经过核心
   Router；未知 `resident.*` 工具名直接 fail-closed（不建 task）。
3. 熔断器落实：派发携带幂等 ID（`idempotency_key`，重复提交返回同一 task，
   不重复执行）；本地执行套 `asyncio.wait_for` 超时隔离；异常只标记 task
   failed，严禁挂起阻塞主进程。

## 验证（Verify）

- `uv run pytest projects/agora/tests/test_resident_a2a.py -q` → exit 0。
- `make gac-local-gate` → exit 0。
- `uv run --with pyyaml python bin/plan/bet-ledger.py lint` → exit 0（结构合法）。

## 决策引用（Decision Ref）

- `decision://accepted/BET-Y1Q4-T5-03`（2026-09-11 UTC，T10-05 done 解锁依赖，可审计）
