---
schema_version: specification/v1
spec_version: 1.0.0
title: OMO 持久 Role/Capsule/Handoff/Claim/Verification/ASD 语义落地设计
bet_id: BET-Y1Q4-T10-165
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-12
---


# T10-165 — OMO 持久语义五件设计

## 1. 问题

Queue/Receipt 基础（task_gateway 七波次 + claims_authority R0）已就绪，
但 Cell 动态编排缺持久身份与可审计交接：

1. **Role 无准入态**：`omo.sovereignty` 有身份模型（`role:` 前缀、assign/
   revoke），但没有面向 Cell 调度的准入状态机（admitted/suspended/
   revoked）与 capabilities 绑定。
2. **无 Capsule 规范**：WorkPacket 流转缺 receipt 绑定的胶囊 envelope，
   跨 Cell 交接不可审计。
3. **Handoff 未入 Mesh**：交接事件未进 Workflow Mesh，旅程断链。
4. **Claim 未绑执行面**：claims_authority R0 仍是 evidence-only，未接入
   task_gateway 执行面。
5. **Verification 停在辅助证据层**：verifier 接口未扩展到 Role 级。
6. **ASD 面板无契约**：驾驶舱（T10-163）五面板缺数据契约与降级规则。

## 2. 非目标 (与 ledger non_goals 一致)

- 不重复 `omo.sovereignty` 身份模型（Role 注册表复用 `role:` ID，只加
  准入状态机层）。
- 未过门零写入/零自治/零扩并发（铁律，检查器固化）。
- 不修改 Merkle 账本格式。

## 3. 设计（分件交付，本 PR = 件一）

### 3.1 件一 · Role 注册表与准入状态机（本 PR）

`projects/omo/src/omo/workflow/role_registry.py`：

- `RoleRecord`: dataclass —— `role_id / capabilities(frozenset) /
  admission_state / version / updated_at`；digest = sha256(规范 JSON)。
- `AdmissionState`: `pending → admitted → suspended → admitted`；
  `admitted/suspended → revoked`（终态）；非法跃迁抛 `RoleRegistryError`。
- `RoleRegistry`: 内存库 + JSONL 落盘；`register()` 校验 `role:` 前缀与
  capabilities 非空；`admit/suspend/revoke` 单调 version 递增；
  stale-version 拒绝。
- `verifier` 钩子：`admit` 要求 capabilities 非空（Role 级 verifier
  接口雏形，件四扩展）。
- 零模型调用，纯确定性逻辑；零写副作用（落盘路径由调用方传入）。

### 3.2 件二 · Capsule（WorkPacket 规范 + receipt 绑定）[后续 PR]

### 3.3 件三 · Handoff 事件入 Mesh（复用 dispatch_backend 模式）[后续 PR]

### 3.4 件四 · Claim 接入 task_gateway + Verification 到 Role 级 [后续 PR]

### 3.5 件五 · ASD 五核心面板数据契约（喂驾驶舱）[后续 PR]

### 3.6 测试（本 PR）

`projects/omo/tests/test_role_registry.py` 覆盖：注册校验（坏前缀/
空 capabilities 拒绝）、admit/suspend/re-admit/revoke 合法链、
非法跃迁（pending→revoked 直跳、revoked 后再变）拒绝、stale-version
拒绝、digest 稳定性。

## 4. 验收

- `uv run pytest projects/omo/tests/test_role_registry.py -q` exit 0
- `make gac-local-gate` exit 0（根仓）
