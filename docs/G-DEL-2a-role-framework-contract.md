---
title: G-DEL.2a 角色框架 + 协作协议契约（仅 spec）
status: active
type: contract
bet: BET-664e3
gate: G-DEL.2a
related:
  - ADR-0210
  - ADR-0220
  - BET-7e074 (G-DEL.1 runtime — NOT this document)
  - docs/STRATEGY-3YEAR-PANORAMA.md
owner: 架构师
created: 2026-07-18
note: >
  Pre-M1 allowed. Spec/interfaces only — no multi-machine registry, scheduler,
  or collab runtime. Implements nothing of G-DEL.1/3/5.
---

# G-DEL.2a · 角色定义框架与协作协议契约

> **范围**：图纸。为 M1 通过后的 G-DEL.2 实现提供可消费契约。  
> **禁止**：多机运行时、Agent 注册中心、分布式调度（属 G-DEL.1）。

## 1. 角色模型（Role Model）

| 字段 | 类型 | 说明 |
|------|------|------|
| `role_id` | string | 稳定 ID，如 `architect` / `implementer` / `verifier` / `scribe` |
| `display_name` | string | 人读名 |
| `capabilities` | string[] | 允许的能力标签（read-docs, write-code, claim-path, merge-pr…） |
| `inputs` | MessageType[] | 可接收的消息类型 |
| `outputs` | MessageType[] | 可发出的消息类型 |
| `completion_semantics` | enum | `done` \| `blocked` \| `handoff` \| `failed` |
| `escalation` | role_id? | 失败/阻塞时默认升级角色 |

### 1.1 最小角色集（兑现期默认）

| role_id | 职责 | 完成语义 |
|---------|------|----------|
| `orchestrator` | 拆 goal、下发 handoff、收口验收 | `done` 当全部子任务 closeout |
| `implementer` | 在 claim 面内改代码/文档 | `handoff` → verifier |
| `verifier` | 跑门禁、写实测数字 | `done` 或 `failed` |
| `scribe` | ADR/INDEX/复盘 | `done` 当 INDEX 一致 |
| `risk-reviewer` | L3 专项评审（G-DEL.5a） | `done` 当 ADR ACCEPTED |

### 1.2 身份与隔离

- **agent_id**：运行实例身份（会话/worktree），≠ role_id。  
- 同一 role 可有多个 agent_id 并发，但 **同一 path claim 互斥**（ADR-0220 D3）。  
- 角色切换不自动继承 path claim。

## 2. 协作协议（Collaboration Protocol）

### 2.1 消息信封

```text
CollabMessage {
  id:            uuid
  type:          MessageType
  from:          { agent_id, role_id }
  to:            { agent_id?, role_id? }   // 可广播 role
  task_ref:      string                   // goal / bet / run-id
  payload:       object
  created_at:    ISO-8601
  correlation_id: uuid?                   // 串联 handoff 链
}
```

### 2.2 MessageType（握手面）

| type | 方向 | 语义 |
|------|------|------|
| `assign` | orchestrator → role | 下发任务 + 验收 KPI |
| `claim_ack` | implementer → orchestrator | path claim 成功 |
| `progress` | any → orchestrator | 进度（非完成） |
| `handoff` | implementer → verifier | 请求验收，附 evidence 指针 |
| `verify_result` | verifier → orchestrator | pass/fail + 实测数字 |
| `block` | any → orchestrator | 阻塞 + 原因码 |
| `complete` | orchestrator → * | 任务 closeout |
| `risk_gate` | risk-reviewer → orchestrator | L3 是否允许实现 |

### 2.3 握手时序（单任务）

```text
orchestrator --assign--> implementer
implementer  --claim_ack--> orchestrator
implementer  --progress*--> orchestrator
implementer  --handoff--> verifier
verifier     --verify_result--> orchestrator
orchestrator --complete--> *
```

失败路径：`block` 或 `verify_result.fail` → orchestrator 决定 reassign / escalate / abort。

## 3. 接口契约（实现期将绑定；本文件只定义）

### 3.1 `RoleRegistry`（本地契约，非分布式调度）

```ts
interface RoleDefinition {
  role_id: string;
  display_name: string;
  capabilities: string[];
  inputs: string[];
  outputs: string[];
  completion_semantics: "done" | "blocked" | "handoff" | "failed";
  escalation?: string;
}

interface RoleRegistry {
  get(role_id: string): RoleDefinition | null;
  list(): RoleDefinition[];
  // NO: schedule(task), registerNode(machine)  — those are G-DEL.1
}
```

### 3.2 `CollabBus`（进程内/本地；多机属 G-DEL.3）

```ts
interface CollabBus {
  publish(msg: CollabMessage): void;
  subscribe(filter: { role_id?: string; type?: string }, handler: (m: CollabMessage) => void): () => void;
  // NO: multi-node fanout, leader election — G-DEL.3
}
```

### 3.3 完成 / 失败语义（执行面门禁挂钩）

| 结果 | 条件 | 写入 |
|------|------|------|
| success | verifier 实测 ≥ KPI | run closeout + metrics JSON |
| failed | verifier 实测 < KPI | fail reason + 可复现命令 |
| blocked | 依赖未就绪（如 M1 未过） | block code `m1_window_open` 等 |

G-DEL.2 实现期 KPI（**不在本 spec 验收**）：角色协作完成率 **> 95%**（BET-664e3）。

## 4. 与相邻 Bet 的边界

| Bet | 关系 |
|-----|------|
| G-DEL.1 / BET-7e074 | 消费本契约的 role_id 做**调度**；本文件不实现注册中心 |
| G-DEL.4 / BET-b7da | handoff payload 可引用 shared-context key；记忆在 gbrain |
| G-DEL.5a | `risk_gate` 消息类型；无风险 ADR 不得实现涌现运行时 |
| G-DEL.3 | 跨机消息可靠投递 — **非本契约** |

## 5. 验收（本 G-DEL.2a）

- [x] 本文档存在于 `docs/G-DEL-2a-role-framework-contract.md`
- [x] 含角色模型、消息/握手、接口、失败/完成语义
- [x] 明确 **无** 多机 registry/scheduler 实现

## 6. 后续（M1 通过后）

1. 在允许运行时落地 `RoleRegistry` + 进程内 `CollabBus`。  
2. 与 G-DEL.1 调度器对接 `assign`/`complete`。  
3. 用真实多角色跑批测协作完成率 > 95%。
